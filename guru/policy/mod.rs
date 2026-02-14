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
    missing_docs
)]
pub mod engine;