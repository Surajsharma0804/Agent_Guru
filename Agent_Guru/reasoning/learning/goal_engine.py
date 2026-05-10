"""Persistent Goal & Trigger Engine.

This module implements a background service that evaluates goal triggers
and executes actions automatically based on time, location, events, or conditions.

Performance Requirements:
- Time Complexity: O(n) for trigger evaluation where n is active goals
- Space Complexity: O(n) where n is total goals
- Latency: <100ms for trigger evaluation, <20ms for state queries

Author: Kiro AI
Date: 2024
"""

import asyncio
import contextlib
import json
import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from Agent_Guru.reasoning.models.goal import (
    GoalExecutionResult,
    GoalStatus,
    PersistentGoal,
    TriggerType,
)

_logger = logging.getLogger(__name__)


class GoalEngine:
    """Persistent goal engine with background trigger evaluation.

    Manages persistent goals that can be triggered automatically based on:
    - Time (specific time of day, day of week, etc.)
    - Location (geofencing)
    - Events (system events, app events)
    - Conditions (world state conditions)

    Time Complexity: O(n) for evaluation where n is active goals
    Space Complexity: O(n) where n is total goals

    Example:
        >>> engine = GoalEngine("goals.db")
        >>> await engine.initialize()
        >>> await engine.start_background_service()
        >>> goal = await engine.register_goal(...)
        >>> await engine.stop_background_service()

    """

    def __init__(
        self,
        db_path: str = "goals.db",
        evaluation_interval: int = 60,
        max_active_goals: int = 50,
        world_state_engine=None,  # noqa: ANN001
    ) -> None:
        """Initialize goal engine.

        Args:
            db_path: Path to SQLite database
            evaluation_interval: Trigger evaluation interval (seconds)
            max_active_goals: Maximum active goals per user
            world_state_engine: WorldStateEngine instance for state queries

        """
        self.db_path = Path(db_path)
        self.evaluation_interval = evaluation_interval
        self.max_active_goals = max_active_goals
        self.world_state_engine = world_state_engine

        self._lock = asyncio.Lock()
        self._initialized = False
        self._background_task: asyncio.Task | None = None
        self._running = False

    async def initialize(self) -> None:
        """Initialize database schema."""
        async with self._lock:
            if self._initialized:
                return

            # Create database directory
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Create tables
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                # Goals table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS persistent_goals (
                        goal_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        description TEXT NOT NULL,
                        trigger_type TEXT NOT NULL,
                        trigger_condition TEXT NOT NULL,
                        action_plan TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'active',
                        created_at TEXT NOT NULL,
                        last_evaluated TEXT,
                        last_triggered TEXT,
                        trigger_count INTEGER NOT NULL DEFAULT 0,
                        notify_before_execution BOOLEAN NOT NULL DEFAULT 1,
                        notification_sent BOOLEAN NOT NULL DEFAULT 0,
                        metadata TEXT NOT NULL DEFAULT '{}'
                    )
                """,
                )

                # Execution history table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS goal_executions (
                        execution_id TEXT PRIMARY KEY,
                        goal_id TEXT NOT NULL,
                        success BOOLEAN NOT NULL,
                        result_data TEXT,
                        error TEXT,
                        execution_time REAL NOT NULL,
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (goal_id) REFERENCES persistent_goals(goal_id)
                    )
                """,
                )

                # Create indexes
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_goals_user_id
                    ON persistent_goals(user_id)
                """,
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_goals_status
                    ON persistent_goals(user_id, status)
                """,
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_goals_trigger_type
                    ON persistent_goals(trigger_type, status)
                """,
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_executions_goal_id
                    ON goal_executions(goal_id, timestamp DESC)
                """,
                )

                conn.commit()
            finally:
                conn.close()

            self._initialized = True

    async def register_goal(self, goal: PersistentGoal) -> PersistentGoal:
        """Register a new persistent goal.

        Time Complexity: O(1)

        Args:
            goal: Goal to register

        Returns:
            Registered goal

        Raises:
            ValueError: If max active goals exceeded

        """
        if not self._initialized:
            await self.initialize()

        # Check active goal limit
        active_count = await self._count_active_goals(goal.user_id)
        if active_count >= self.max_active_goals:
            msg = f"Maximum active goals ({self.max_active_goals}) exceeded for user {goal.user_id}"
            raise ValueError(
                msg,
            )

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO persistent_goals (
                        goal_id, user_id, description, trigger_type,
                        trigger_condition, action_plan, status, created_at,
                        last_evaluated, last_triggered, trigger_count,
                        notify_before_execution, notification_sent, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        goal.goal_id,
                        goal.user_id,
                        goal.description,
                        goal.trigger_type.value,
                        json.dumps(goal.trigger_condition),
                        json.dumps(goal.action_plan),
                        goal.status.value,
                        goal.created_at.isoformat(),
                        goal.last_evaluated.isoformat() if goal.last_evaluated else None,
                        goal.last_triggered.isoformat() if goal.last_triggered else None,
                        goal.trigger_count,
                        goal.notify_before_execution,
                        goal.notification_sent,
                        json.dumps(goal.metadata),
                    ),
                )
                conn.commit()
                return goal
            finally:
                conn.close()

    async def update_goal(self, goal_id: str, updates: dict) -> PersistentGoal | None:
        """Update goal properties.

        Args:
            goal_id: Goal identifier
            updates: Dictionary of fields to update

        Returns:
            Updated goal or None if not found

        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                # Allowlist of valid column names to prevent SQL injection
                _ALLOWED_UPDATE_KEYS = frozenset(
                    {
                        "trigger_condition",
                        "action_plan",
                        "metadata",
                        "last_evaluated",
                        "last_triggered",
                        "created_at",
                        "status",
                        "description",
                        "trigger_type",
                        "notify_before_execution",
                        "notification_sent",
                        "trigger_count",
                    },
                )

                # Build update query
                set_clauses = []
                values = []
                for key, value in updates.items():
                    if key not in _ALLOWED_UPDATE_KEYS:
                        msg = f"Invalid update key: {key!r}"
                        raise ValueError(msg)
                    if key in ["trigger_condition", "action_plan", "metadata"]:
                        set_clauses.append(key + " = ?")
                        values.append(json.dumps(value))
                    elif key in ["last_evaluated", "last_triggered", "created_at"]:
                        set_clauses.append(key + " = ?")
                        iso_value = value.isoformat() if value else None
                        values.append(str(iso_value) if iso_value is not None else "")
                    else:
                        set_clauses.append(key + " = ?")
                        values.append(value)

                if not set_clauses:
                    return await self.get_goal(goal_id)

                values.append(goal_id)
                # Build query — column names are validated against allowlist above; values are parameterized
                query = (
                    "UPDATE persistent_goals SET " + ", ".join(set_clauses) + " WHERE goal_id = ?"  # nosec B608  # noqa: S608 - SQL parameterization reviewed
                )

                cursor.execute(query, values)
                conn.commit()

                return await self.get_goal(goal_id)
            finally:
                conn.close()

    async def cancel_goal(self, goal_id: str) -> bool:
        """Cancel a goal.

        Args:
            goal_id: Goal identifier

        Returns:
            True if cancelled, False if not found

        """
        return await self._update_goal_status(goal_id, GoalStatus.CANCELLED)

    async def pause_goal(self, goal_id: str) -> bool:
        """Pause a goal.

        Args:
            goal_id: Goal identifier

        Returns:
            True if paused, False if not found

        """
        return await self._update_goal_status(goal_id, GoalStatus.PAUSED)

    async def resume_goal(self, goal_id: str) -> bool:
        """Resume a paused goal.

        Args:
            goal_id: Goal identifier

        Returns:
            True if resumed, False if not found

        """
        return await self._update_goal_status(goal_id, GoalStatus.ACTIVE)

    async def _update_goal_status(self, goal_id: str, status: GoalStatus) -> bool:
        """Update goal status."""
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE persistent_goals
                    SET status = ?
                    WHERE goal_id = ?
                """,
                    (status.value, goal_id),
                )
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    async def get_goal(self, goal_id: str) -> PersistentGoal | None:
        """Get goal by ID.

        Time Complexity: O(1) with index

        Args:
            goal_id: Goal identifier

        Returns:
            Goal or None if not found

        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM persistent_goals
                    WHERE goal_id = ?
                """,
                    (goal_id,),
                )
                row = cursor.fetchone()
                return self._row_to_goal(row) if row else None
            finally:
                conn.close()

    async def get_active_goals(self, user_id: str | None = None) -> list[PersistentGoal]:
        """Get all active goals.

        Time Complexity: O(n) where n is active goals

        Args:
            user_id: Filter by user (optional)

        Returns:
            List of active goals

        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                if user_id:
                    cursor.execute(
                        """
                        SELECT * FROM persistent_goals
                        WHERE user_id = ? AND status = 'active'
                        ORDER BY created_at DESC
                    """,
                        (user_id,),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT * FROM persistent_goals
                        WHERE status = 'active'
                        ORDER BY created_at DESC
                    """,
                    )

                rows = cursor.fetchall()
                return [self._row_to_goal(row) for row in rows]
            finally:
                conn.close()

    async def get_goal_history(self, user_id: str, limit: int = 100) -> list[PersistentGoal]:
        """Get goal history for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of goals

        Returns:
            List of goals

        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM persistent_goals
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (user_id, limit),
                )
                rows = cursor.fetchall()
                return [self._row_to_goal(row) for row in rows]
            finally:
                conn.close()

    async def record_execution(self, result: GoalExecutionResult) -> None:
        """Record goal execution result.

        Args:
            result: Execution result

        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO goal_executions (
                        execution_id, goal_id, success, result_data,
                        error, execution_time, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        str(uuid.uuid4()),
                        result.goal_id,
                        result.success,
                        json.dumps(result.result_data) if result.result_data else None,
                        result.error,
                        result.execution_time,
                        result.timestamp.isoformat(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    async def start_background_service(self) -> None:
        """Start background trigger evaluation service."""
        if self._running:
            return

        self._running = True
        self._background_task = asyncio.create_task(self._evaluation_loop())

    async def stop_background_service(self) -> None:
        """Stop background trigger evaluation service."""
        self._running = False
        if self._background_task:
            self._background_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._background_task
            self._background_task = None

    async def _evaluation_loop(self) -> None:
        """Background loop for trigger evaluation."""
        while self._running:
            try:
                await self.evaluate_triggers()
                await asyncio.sleep(self.evaluation_interval)
            except asyncio.CancelledError:
                break
                # Log error but continue running
                _logger.exception("Error in goal evaluation loop")
                await asyncio.sleep(self.evaluation_interval)
    async def evaluate_triggers(self) -> list[PersistentGoal]:
        """Evaluate all active goal triggers.

        Time Complexity: O(n) where n is active goals

        Returns:
            List of triggered goals

        """
        if not self._initialized:
            await self.initialize()

        # Get all active goals
        active_goals = await self.get_active_goals()

        triggered = []
        for goal in active_goals:
            # Mark as evaluated
            goal.mark_evaluated()
            await self.update_goal(goal.goal_id, {"last_evaluated": goal.last_evaluated})

            # Check if can trigger (respects minimum interval)
            if not goal.can_trigger(min_interval_seconds=3600):  # 1 hour minimum
                continue

            # Evaluate trigger based on type
            should_trigger = False

            if goal.trigger_type == TriggerType.TIME_BASED:
                should_trigger = await self._evaluate_time_trigger(goal)
            elif goal.trigger_type == TriggerType.LOCATION_BASED:
                should_trigger = await self._evaluate_location_trigger(goal)
            elif goal.trigger_type == TriggerType.EVENT_BASED:
                should_trigger = await self._evaluate_event_trigger(goal)
            elif goal.trigger_type == TriggerType.CONDITIONAL:
                should_trigger = await self._evaluate_conditional_trigger(goal)

            if should_trigger:
                triggered.append(goal)

        return triggered

    async def _evaluate_time_trigger(self, goal: PersistentGoal) -> bool:
        """Evaluate time-based trigger.

        Checks if current time matches trigger condition.

        Args:
            goal: Goal with time-based trigger

        Returns:
            True if trigger condition is met

        """
        from Agent_Guru.reasoning.models.goal import TimeBasedTrigger

        trigger = TimeBasedTrigger(**goal.trigger_condition)
        now = datetime.now(tz=UTC)

        # Parse time_of_day
        hour, minute = map(int, trigger.time_of_day.split(":"))

        # Check time match (within 1 minute window)
        time_match = now.hour == hour and abs(now.minute - minute) <= 1

        if not time_match:
            return False

        # Check day of week if specified
        if trigger.day_of_week is not None and now.weekday() != trigger.day_of_week:
            return False

        # Check day of month if specified
        if trigger.day_of_month is not None and now.day != trigger.day_of_month:
            return False

        # Check recurrence
        if trigger.recurrence == "once":
            # Only trigger if never triggered before
            return goal.trigger_count == 0

        return True

    async def _evaluate_location_trigger(self, goal: PersistentGoal) -> bool:
        """Evaluate location-based trigger.

        Checks if current location is within geofence using WorldState.

        Args:
            goal: Goal with location-based trigger

        Returns:
            True if trigger condition is met

        """
        from Agent_Guru.reasoning.models.goal import LocationBasedTrigger

        trigger = LocationBasedTrigger(**goal.trigger_condition)

        # Get current location from WorldState
        if self.world_state_engine is None:
            return False

        try:
            world_state = await self.world_state_engine.get_state(goal.user_id)
            if world_state is None or world_state.location_context is None:
                return False

            current_location = world_state.location_context

            # Calculate distance using Haversine formula
            import math

            lat1, lon1 = math.radians(trigger.latitude), math.radians(trigger.longitude)
            lat2, lon2 = (
                math.radians(current_location.latitude),
                math.radians(current_location.longitude),
            )

            dlat = lat2 - lat1
            dlon = lon2 - lon1

            a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
            c = 2 * math.asin(math.sqrt(a))
            distance = 6371000 * c  # Earth radius in meters

            # Check trigger condition
            if trigger.trigger_on == "enter":
                # Trigger when entering geofence
                return distance <= trigger.radius
            if trigger.trigger_on == "exit":
                # Trigger when exiting geofence
                return distance > trigger.radius
            if trigger.trigger_on == "dwell":
                # Trigger when dwelling in geofence
                return distance <= trigger.radius

            return False
        except Exception as e:
            _logger.warning("Error evaluating location trigger: %s", e)
            return False
    async def _evaluate_event_trigger(self, goal: PersistentGoal) -> bool:
        """Evaluate event-based trigger.

        Checks if specified event has occurred using WorldState.

        Args:
            goal: Goal with event-based trigger

        Returns:
            True if trigger condition is met

        """
        from Agent_Guru.reasoning.models.goal import EventBasedTrigger

        trigger = EventBasedTrigger(**goal.trigger_condition)

        # Get recent activities from WorldState
        if self.world_state_engine is None:
            return False

        try:
            world_state = await self.world_state_engine.get_state(goal.user_id)
            if world_state is None:
                return False

            # Check recent activities for matching event
            for activity in world_state.recent_activities:
                if activity.activity_type == trigger.event_type:
                    # Check event filter
                    if self._matches_event_filter(activity.details, trigger.event_filter):
                        return True

            return False
        except Exception as e:
            _logger.warning("Error evaluating event trigger: %s", e)
            return False
    def _matches_event_filter(self, event_data: dict, event_filter: dict) -> bool:
        """Check if event data matches filter criteria.

        Args:
            event_data: Event data to check
            event_filter: Filter criteria

        Returns:
            True if event matches filter

        """
        if not event_filter:
            return True

        for key, value in event_filter.items():
            if key not in event_data or event_data[key] != value:
                return False

        return True

    async def _evaluate_conditional_trigger(self, goal: PersistentGoal) -> bool:
        """Evaluate conditional trigger.

        Evaluates boolean expression against WorldState.

        Args:
            goal: Goal with conditional trigger

        Returns:
            True if trigger condition is met

        """
        from Agent_Guru.reasoning.models.goal import ConditionalTrigger

        trigger = ConditionalTrigger(**goal.trigger_condition)

        # Get WorldState
        if self.world_state_engine is None:
            return False

        try:
            world_state = await self.world_state_engine.get_state(goal.user_id)
            if world_state is None:
                return False

            # Evaluate condition expression safely
            # Create safe evaluation context with WorldState data
            context = {
                "battery_level": (
                    world_state.device_status.battery_level if world_state.device_status else 0
                ),
                "charging": (
                    world_state.device_status.charging if world_state.device_status else False
                ),
                "network_type": (
                    world_state.device_status.network_type
                    if world_state.device_status
                    else "unknown"
                ),
                "do_not_disturb": (
                    world_state.device_status.do_not_disturb if world_state.device_status else False
                ),
                "active_apps_count": len(world_state.active_apps),
                "has_location": world_state.location_context is not None,
            }

            # Safely evaluate expression
            # (Using simple comparison operators only for safety)
            return self._safe_eval_condition(trigger.condition_expression, context)

        except Exception as e:
            _logger.warning("Error evaluating conditional trigger: %s", e)
            return False
    def _safe_eval_condition(self, expression: str, context: dict) -> bool:
        """Safely evaluate boolean expression.

        Only allows simple comparisons for security.

        Args:
            expression: Boolean expression
            context: Variable context

        Returns:
            Evaluation result

        """
        # Simple safe evaluation using ast module instead of eval
        import ast
        import operator

        # Define safe operators
        safe_operators = {
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.Lt: operator.lt,
            ast.LtE: operator.le,
            ast.Gt: operator.gt,
            ast.GtE: operator.ge,
            ast.And: operator.and_,
            ast.Or: operator.or_,
            ast.Not: operator.not_,
        }

        try:
            # Parse expression into AST
            tree = ast.parse(expression, mode="eval")

            # Evaluate AST safely
            def eval_node(node):  # noqa: ANN001
                if isinstance(node, ast.Expression):
                    return eval_node(node.body)
                if isinstance(node, ast.Compare):
                    left = eval_node(node.left)
                    for op, comparator in zip(node.ops, node.comparators, strict=True):
                        if type(op) not in safe_operators:
                            msg = f"Unsafe operator: {type(op)}"
                            raise ValueError(msg)
                        right = eval_node(comparator)
                        op_func = safe_operators[type(op)]
                        if not op_func(left, right):
                            return False
                        left = right
                    return True
                if isinstance(node, ast.BoolOp):
                    if type(node.op) not in safe_operators:
                        msg = f"Unsafe operator: {type(node.op)}"
                        raise ValueError(msg)
                    values = [eval_node(v) for v in node.values]
                    if isinstance(node.op, ast.And):
                        return all(values)
                    if isinstance(node.op, ast.Or):
                        return any(values)
                elif isinstance(node, ast.UnaryOp):
                    if type(node.op) not in safe_operators:
                        msg = f"Unsafe operator: {type(node.op)}"
                        raise ValueError(msg)
                    op_func = safe_operators[type(node.op)]
                    return op_func(eval_node(node.operand))
                elif isinstance(node, ast.Name):
                    if node.id not in context:
                        msg = f"Unknown variable: {node.id}"
                        raise ValueError(msg)
                    return context[node.id]
                elif isinstance(node, ast.Constant):
                    return node.value
                elif isinstance(node, ast.Num):  # Python 3.7 compatibility
                    return node.n
                elif isinstance(node, ast.Str):  # Python 3.7 compatibility
                    return node.s
                elif isinstance(node, ast.NameConstant):  # Python 3.7 compatibility
                    return node.value
                else:
                    msg = f"Unsupported node type: {type(node)}"
                    raise ValueError(msg)
                return None

            result = eval_node(tree)
            return bool(result)

        except Exception as e:
            _logger.warning("Error evaluating condition %r: %s", expression, e)
            return False
    async def execute_triggered_goal(self, goal: PersistentGoal) -> GoalExecutionResult:
        """Execute a triggered goal.

        Execution flow:
        1. Check safety constraints
        2. Check if notification required
        3. Send notification if needed
        4. Wait for user confirmation (if required)
        5. Execute action plan
        6. Update goal status and trigger count
        7. Log execution result

        Args:
            goal: Goal to execute

        Returns:
            Execution result

        """
        start_time = datetime.now(tz=UTC)

        try:
            # Check safety constraints
            safety_check = await self._check_goal_safety(goal)
            if not safety_check["allowed"]:
                msg = f"Goal execution blocked: {safety_check['reason']}"
                raise ValueError(msg)

            # Check if notification required
            if goal.notify_before_execution and not goal.notification_sent:
                # Send notification
                await self._send_notification(goal)
                goal.notification_sent = True
                await self.update_goal(goal.goal_id, {"notification_sent": True})

                # Wait for user confirmation
                # (This would integrate with notification system)
                # For now, assume confirmation granted
                # TODO: Implement confirmation waiting logic

            # Execute action plan
            # (This would integrate with execution pipeline)
            # For now, simulate execution
            # TODO: Integrate with standard execution pipeline
            result_data = {"message": "Goal executed successfully"}
            success = True
            error = None

            # Mark goal as triggered
            goal.mark_triggered()
            await self.update_goal(
                goal.goal_id,
                {
                    "last_triggered": goal.last_triggered,
                    "trigger_count": goal.trigger_count,
                    "notification_sent": False,  # Reset for next trigger
                },
            )

            # Calculate execution time
            execution_time = (datetime.now(tz=UTC) - start_time).total_seconds()

            # Create result
            result = GoalExecutionResult(
                goal_id=goal.goal_id,
                success=success,
                result_data=result_data,
                error=error,
                execution_time=execution_time,
                timestamp=datetime.now(tz=UTC),
            )

            # Record execution
            await self.record_execution(result)

            return result

        except Exception as e:
            # Handle execution error
            execution_time = (datetime.now(tz=UTC) - start_time).total_seconds()
            result = GoalExecutionResult(
                goal_id=goal.goal_id,
                success=False,
                result_data=None,
                error=str(e),
                execution_time=execution_time,
                timestamp=datetime.now(tz=UTC),
            )
            # Record failed execution
            await self.record_execution(result)
            # Check for consecutive failures
            await self._check_failure_threshold(goal)
            return result
    async def _send_notification(self, goal: PersistentGoal) -> None:
        """Send notification to user before execution.

        Args:
            goal: Goal to notify about

        """
        # TODO: Integrate with notification system
        # For now, just log
        _logger.info("Goal '%s' is about to execute (notification stub)", goal.description)

    async def _check_goal_safety(self, goal: PersistentGoal) -> dict:
        """Check if goal execution is safe.

        Safety checks:
        - Trigger frequency limit (max once per hour)
        - Sensitive action confirmation required
        - User control enabled
        - Not disabled due to failures

        Args:
            goal: Goal to check

        Returns:
            Dictionary with 'allowed' (bool) and 'reason' (str)

        """
        # Check if goal is active
        if goal.status != GoalStatus.ACTIVE:
            return {"allowed": False, "reason": f"Goal status is {goal.status.value}"}

        # Check trigger frequency (max once per hour)
        if not goal.can_trigger(min_interval_seconds=3600):
            return {
                "allowed": False,
                "reason": "Trigger frequency limit exceeded (max once per hour)",
            }

        # Check if action requires confirmation
        action_plan = goal.action_plan
        if self._is_sensitive_action(action_plan):
            if goal.notify_before_execution and not goal.notification_sent:
                return {
                    "allowed": False,
                    "reason": "Sensitive action requires user confirmation",
                }

        # Check recent failure rate
        recent_failures = await self._get_recent_failure_count(goal.goal_id, limit=5)
        if recent_failures >= 5:  # noqa: PLR2004 - Small integer threshold

            return {
                "allowed": False,
                "reason": "Goal disabled after 5 consecutive failures",
            }

        return {"allowed": True, "reason": ""}

    def _is_sensitive_action(self, action_plan: dict) -> bool:
        """Check if action plan contains sensitive actions.

        Sensitive actions include:
        - Messaging/calling
        - Smart home control
        - File operations
        - Financial transactions

        Args:
            action_plan: Action plan to check

        Returns:
            True if action is sensitive

        """
        # Check action type
        action_type = action_plan.get("type", "")
        sensitive_types = [
            "send_message",
            "make_call",
            "smart_home_control",
            "file_delete",
            "file_modify",
            "financial_transaction",
        ]

        return action_type in sensitive_types

    async def _get_recent_failure_count(self, goal_id: str, limit: int = 5) -> int:
        """Get count of recent consecutive failures.

        Args:
            goal_id: Goal identifier
            limit: Number of recent executions to check

        Returns:
            Number of consecutive failures

        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT success FROM goal_executions
                WHERE goal_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (goal_id, limit),
            )
            recent_executions = [row[0] for row in cursor.fetchall()]

            # Count consecutive failures from most recent
            failure_count = 0
            for success in recent_executions:
                if not success:
                    failure_count += 1
                else:
                    break

            return failure_count
        finally:
            conn.close()

    async def get_goal_metrics(self, goal_id: str) -> dict:
        """Get execution metrics for a goal.

        Args:
            goal_id: Goal identifier

        Returns:
            Metrics dictionary

        """
        if not self._initialized:
            await self.initialize()

        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()

            # Get execution stats
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_executions,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_executions,
                    AVG(execution_time) as avg_execution_time,
                    MAX(timestamp) as last_execution
                FROM goal_executions
                WHERE goal_id = ?
            """,
                (goal_id,),
            )
            row = cursor.fetchone()

            total = row[0] or 0
            successful = row[1] or 0
            avg_time = row[2] or 0.0
            last_exec = row[3]

            return {
                "goal_id": goal_id,
                "total_executions": total,
                "successful_executions": successful,
                "failed_executions": total - successful,
                "success_rate": successful / total if total > 0 else 0.0,
                "avg_execution_time": avg_time,
                "last_execution": last_exec,
            }
        finally:
            conn.close()

    async def _check_failure_threshold(self, goal: PersistentGoal) -> None:
        """Check if goal has exceeded failure threshold.

        Disables goal after 5 consecutive failures.

        Args:
            goal: Goal to check

        """
        # Get recent executions
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT success FROM goal_executions
                WHERE goal_id = ?
                ORDER BY timestamp DESC
                LIMIT 5
            """,
                (goal.goal_id,),
            )
            recent_executions = [row[0] for row in cursor.fetchall()]

            # Check if last 5 executions all failed
            if len(recent_executions) >= 5 and not any(recent_executions):  # noqa: PLR2004 - Small integer threshold

                # Disable goal
                await self.pause_goal(goal.goal_id)
                _logger.warning("Goal '%s' paused after 5 consecutive failures", goal.description)
        finally:
            conn.close()

    async def _count_active_goals(self, user_id: str) -> int:
        """Count active goals for a user."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) FROM persistent_goals
                WHERE user_id = ? AND status = 'active'
            """,
                (user_id,),
            )
            result = cursor.fetchone()
            return int(result[0]) if result else 0
        finally:
            conn.close()

    def _row_to_goal(self, row: tuple) -> PersistentGoal:
        """Convert database row to PersistentGoal object."""
        return PersistentGoal(
            goal_id=row[0],
            user_id=row[1],
            description=row[2],
            trigger_type=TriggerType(row[3]),
            trigger_condition=json.loads(row[4]),
            action_plan=json.loads(row[5]),
            status=GoalStatus(row[6]),
            created_at=datetime.fromisoformat(row[7]),
            last_evaluated=datetime.fromisoformat(row[8]) if row[8] else None,
            last_triggered=datetime.fromisoformat(row[9]) if row[9] else None,
            trigger_count=row[10],
            notify_before_execution=bool(row[11]),
            notification_sent=bool(row[12]),
            metadata=json.loads(row[13]),
        )
