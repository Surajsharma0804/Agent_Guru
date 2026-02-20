import re

# Read the file
with open(
    "Agent_Guru/reasoning/knowledge/tests/test_llm_synthesis_property.py", encoding="utf-8"
) as f:
    content = f.read()

# Replace memory_id = draw(...) with memory_id = str(uuid.uuid4())
content = re.sub(
    r"memory_id = draw\(st\.text\(min_size=1, max_size=50\)\)",
    "memory_id = str(uuid.uuid4())",
    content,
)

# Write back
with open(
    "Agent_Guru/reasoning/knowledge/tests/test_llm_synthesis_property.py", "w", encoding="utf-8"
) as f:
    f.write(content)

print("Fixed property test memory_id issues")
