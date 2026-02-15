//! # Policy Engine Module
//! 
//! Production-grade policy evaluation with cryptographic governance.

#![deny(clippy::all, clippy::pedantic, clippy::nursery)]
#![allow(
    clippy::module_name_repetitions,
    clippy::missing_errors_doc,
    clippy::unnecessary_wraps,
    clippy::cast_possible_truncation,
    clippy::unused_self,
    clippy::too_many_arguments,
    clippy::ptr_arg,
    clippy::manual_clamp,
    clippy::inherent_to_string,
    clippy::await_holding_lock,
    clippy::needless_range_loop,
    clippy::manual_memcpy,
    clippy::suboptimal_flops,
    clippy::struct_excessive_bools,
    clippy::cast_precision_loss,
    clippy::cast_sign_loss,
    clippy::cast_lossless,
    clippy::or_fun_call,
    clippy::significant_drop_tightening,
    clippy::missing_panics_doc,
    clippy::redundant_closure_for_method_calls,
    clippy::needless_borrow,
    clippy::too_many_lines,
    clippy::derive_partial_eq_without_eq,
    clippy::type_complexity,
    clippy::match_same_arms,
    clippy::only_used_in_recursion,
    clippy::trivially_copy_pass_by_ref,
    clippy::single_element_loop,
    clippy::option_if_let_else,
    clippy::cast_possible_wrap,
    clippy::items_after_statements,
    clippy::ref_patterns,
    clippy::bool_comparison,
    clippy::needless_pass_by_value,
    clippy::wildcard_enum_match_arm,
    missing_docs
)]
pub mod engine;