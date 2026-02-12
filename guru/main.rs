//! # AGENT_GURU Main Entry Point
//! 
//! Production-grade sovereign AI operating companion with multi-provider LLM routing.
//! Supports local models (Ollama) and cloud APIs (OpenAI, Gemini) with runtime switching.

use agent_guru::{
    self,
    llm::{
        ApiCredentials, ChatMessage, ModelRouter, TaskType, UnifiedProvider,
        load_config_or_default,
    },
};
use std::io::{self, Write};
use std::path::PathBuf;
use std::process;

#[tokio::main]
async fn main() {
    // Initialize the system
    if let Err(e) = agent_guru::init() {
        eprintln!("Failed to initialize AGENT_GURU: {}", e);
        process::exit(1);
    }
    
    println!("╔════════════════════════════════════════════════════════════╗");
    println!("║          AGENT_GURU {} - Sovereign AI Companion          ║", agent_guru::VERSION);
    println!("╚════════════════════════════════════════════════════════════╝");
    println!();
    
    // Load LLM configuration
    let config_path = PathBuf::from(".kiro/llm_config.yaml");
    let llm_config = load_config_or_default(&config_path);
    
    println!("LLM Configuration:");
    println!("  Mode: {:?}", llm_config.mode);
    println!("  Default Provider: {:?}", llm_config.default_provider);
    println!("  API Confirmation Required: {}", llm_config.require_user_confirmation_for_api);
    println!();
    
    // Load API credentials from environment
    let credentials = ApiCredentials::from_env();
    
    // Initialize unified provider
    let audit_log_path = PathBuf::from(".kiro/logs/llm_audit.jsonl");
    let mut unified_provider = match UnifiedProvider::new(
        llm_config.clone(),
        credentials,
        audit_log_path,
    ) {
        Ok(provider) => provider,
        Err(e) => {
            eprintln!("Failed to initialize LLM provider: {}", e);
            eprintln!("Check configuration and API keys.");
            process::exit(1);
        }
    };
    
    // Initialize simple multi-model router for backward compatibility
    let mut router = ModelRouter::new(
        "mistral:7b-instruct".to_string(),
        "qwen2.5:14b-instruct".to_string(),
        "qwen2.5:14b-instruct".to_string(),
    );
    
    // Check model availability
    print!("Checking model availability... ");
    io::stdout().flush().unwrap();
    
    let availability = router.check_availability().await;
    println!();
    println!("  Fast Model (mistral:7b):      {}", if availability.fast_available { "✓" } else { "✗" });
    println!("  Balanced Model (qwen2.5:14b): {}", if availability.balanced_available { "✓" } else { "✗" });
    println!("  Complex Model (qwen2.5:14b):  {}", if availability.complex_available { "✓" } else { "✗" });
    
    let all_available = availability.fast_available && availability.balanced_available && availability.complex_available;
    
    if !all_available {
        println!();
        println!("Warning: Some models are not available.");
        println!("Note: Ollama may not be running. Start it with: ollama serve");
        println!("      Ensure models are pulled: ollama pull mistral:7b-instruct");
        println!("                                 ollama pull qwen2.5:14b-instruct");
    }
    
    println!();
    println!("System Status: OPERATIONAL");
    println!("Security: Cryptographic identity enabled");
    println!("Mode: Multi-Provider Intelligent Routing");
    println!();
    println!("💬 CONVERSATIONAL MODE ACTIVE");
    println!("   Talk to me naturally - I'm here to chat like a friend!");
    println!();
    println!("Commands:");
    println!("  help     - Show available commands");
    println!("  status   - Show system status");
    println!("  stats    - Show model performance statistics");
    println!("  audit    - Show audit statistics");
    println!("  provider - Show provider configuration");
    println!("  clear    - Clear conversation history");
    println!("  exit     - Exit AGENT_GURU");
    println!();
    println!("💡 Tip: Just type naturally! Ask me anything, share your thoughts,");
    println!("   or chat about your day. I'm here to be your AI companion.");
    println!();
    
    let use_unified = false; // Toggle between simple router and unified provider
    
    // Conversation history with system prompt for friendly conversation
    let mut conversation: Vec<ChatMessage> = vec![
        ChatMessage {
            role: "system".to_string(),
            content: "You are GURU, a friendly AI companion. You talk naturally like a good friend - warm, supportive, and genuinely interested in the conversation. You're knowledgeable but never condescending. You use casual language when appropriate, share insights thoughtfully, and make the user feel comfortable. You're here to chat, help, and be a great companion.".to_string(),
        }
    ];
    
    // Interactive loop
    loop {
        print!("GURU> ");
        io::stdout().flush().unwrap();
        
        let mut input = String::new();
        if io::stdin().read_line(&mut input).is_err() {
            eprintln!("Error reading input");
            continue;
        }
        
        let command = input.trim();
        
        if command.is_empty() {
            continue;
        }
        
        match command {
            "help" => {
                println!("\n╔═══════════════════════════════════════════════════════╗");
                println!("║              AGENT_GURU - Your AI Friend              ║");
                println!("╚═══════════════════════════════════════════════════════╝");
                println!();
                println!("Hey! I'm GURU, your AI companion. Here's how we can interact:");
                println!();
                println!("🗨️  Natural Conversation:");
                println!("   Just type anything! Ask questions, share thoughts, or chat");
                println!("   about your day. I'm here to listen and help.");
                println!();
                println!("   Examples:");
                println!("   • \"How are you today?\"");
                println!("   • \"Can you explain quantum computing?\"");
                println!("   • \"I'm working on a Rust project, any tips?\"");
                println!("   • \"Tell me something interesting!\"");
                println!();
                println!("⚙️  System Commands:");
                println!("   help     - Show this help message");
                println!("   status   - Display system status and metrics");
                println!("   stats    - Show model performance statistics");
                println!("   audit    - Show audit log statistics");
                println!("   provider - Show provider configuration");
                println!("   clear    - Clear conversation history (fresh start)");
                println!("   exit     - Say goodbye and exit");
                println!();
                println!("🤖 About Me:");
                println!("   I use multiple AI models to give you the best responses:");
                println!("   • Fast model for quick questions (≤ 200ms)");
                println!("   • Balanced model for general chat");
                println!("   • Complex model for deep reasoning");
                println!();
                println!("   I can work with local models (private) or cloud APIs");
                println!("   (OpenAI, Gemini) based on your configuration.");
                println!();
                println!("💡 Pro Tip: I remember our conversation, so feel free to");
                println!("   refer back to things we discussed earlier!");
                println!();
            }
            "status" => {
                println!("\n╔═══════════════════════════════════════╗");
                println!("║        AGENT_GURU System Status       ║");
                println!("╚═══════════════════════════════════════╝");
                println!("Version:        {}", agent_guru::VERSION);
                println!("Status:         OPERATIONAL");
                println!("Security:       ENABLED");
                println!("Platform:       {}", std::env::consts::OS);
                println!("Architecture:   {}", std::env::consts::ARCH);
                println!("Routing:        Multi-Provider Intelligent");
                println!("LLM Mode:       {:?}", llm_config.mode);
                println!("Conversation:   {} messages", conversation.len());
                println!();
            }
            "audit" => {
                match unified_provider.get_audit_statistics() {
                    Ok(stats) => {
                        println!("\n╔═══════════════════════════════════════════════════════╗");
                        println!("║           Audit Log Statistics                        ║");
                        println!("╚═══════════════════════════════════════════════════════╝");
                        println!("Total Operations:     {}", stats.total_operations);
                        println!("Successful:           {} ({:.1}%)", 
                            stats.successful_operations,
                            if stats.total_operations > 0 {
                                (stats.successful_operations as f64 / stats.total_operations as f64) * 100.0
                            } else {
                                0.0
                            }
                        );
                        println!("Failed:               {}", stats.failed_operations);
                        println!("Fallback Used:        {}", stats.fallback_operations);
                        println!("Average Latency:      {}ms", stats.avg_latency_ms);
                        println!();
                    }
                    Err(e) => {
                        println!("Error reading audit log: {}", e);
                        println!();
                    }
                }
            }
            "provider" => {
                println!("\n╔═══════════════════════════════════════════════════════╗");
                println!("║           Provider Configuration                      ║");
                println!("╚═══════════════════════════════════════════════════════╝");
                println!("Mode: {:?}", llm_config.mode);
                println!("Default Provider: {:?}", llm_config.default_provider);
                println!();
                println!("Task Configuration:");
                for (task, config) in &llm_config.tasks {
                    println!("  {:?}:", task);
                    println!("    Provider: {:?}", config.provider);
                    println!("    Model: {}", config.model);
                    if let Some(fb_provider) = config.fallback_provider {
                        println!("    Fallback Provider: {:?}", fb_provider);
                        if let Some(fb_model) = &config.fallback_model {
                            println!("    Fallback Model: {}", fb_model);
                        }
                    }
                }
                println!();
                println!("Configuration file: .kiro/llm_config.yaml");
                println!("Documentation: LLM_RUNTIME_AND_PROVIDER_SWITCHING.md");
                println!();
            }
            "stats" => {
                let stats = router.get_performance_stats();
                println!("\n╔═══════════════════════════════════════════════════════╗");
                println!("║           Model Performance Statistics                ║");
                println!("╚═══════════════════════════════════════════════════════╝");
                println!("Total Queries:  {}", stats.total_queries);
                println!();
                println!("Fast Model (mistral:7b):");
                println!("  Queries:      {}", stats.fast_query_count);
                println!("  Avg Latency:  {:.0}ms", stats.fast_avg_latency_ms);
                println!();
                println!("Balanced Model (qwen2.5:14b):");
                println!("  Queries:      {}", stats.balanced_query_count);
                println!("  Avg Latency:  {:.0}ms", stats.balanced_avg_latency_ms);
                println!();
                println!("Complex Model (qwen2.5:14b):");
                println!("  Queries:      {}", stats.complex_query_count);
                println!("  Avg Latency:  {:.0}ms", stats.complex_avg_latency_ms);
                println!();
            }
            "clear" => {
                conversation.clear();
                // Re-add system prompt
                conversation.push(ChatMessage {
                    role: "system".to_string(),
                    content: "You are GURU, a friendly AI companion. You talk naturally like a good friend - warm, supportive, and genuinely interested in the conversation. You're knowledgeable but never condescending. You use casual language when appropriate, share insights thoughtfully, and make the user feel comfortable. You're here to chat, help, and be a great companion.".to_string(),
                });
                println!("\n✨ Fresh start! Our conversation history has been cleared.");
                println!("   Let's chat about something new!\n");
            }
            "exit" | "quit" | "bye" | "goodbye" => {
                println!("\n👋 Thanks for chatting with me! It was great talking to you.");
                println!("   See you next time, friend!");
                println!();
                break;
            }
            _ => {
                // Natural language input - route to appropriate model
                if !all_available {
                    println!("❌ Oops! The AI models aren't available right now.");
                    println!("   Please start Ollama with: ollama serve");
                    println!();
                    continue;
                }
                
                // Add user message to conversation
                conversation.push(ChatMessage {
                    role: "user".to_string(),
                    content: command.to_string(),
                });
                
                print!("\n🤖 GURU: ");
                io::stdout().flush().unwrap();
                
                // Choose between simple router and unified provider
                if use_unified {
                    // Use unified provider with task-based routing
                    match unified_provider.execute_task(
                        TaskType::LanguageHelp,
                        conversation.clone(),
                    ).await {
                        Ok(response) => {
                            println!("{}", response.content);
                            println!("\n   [Provider: {:?} | Model: {} | {}ms{}]", 
                                response.provider,
                                response.model,
                                response.latency_ms,
                                if response.fallback_used { " | Fallback" } else { "" }
                            );
                            println!();
                            
                            // Add assistant response to conversation
                            conversation.push(ChatMessage {
                                role: "assistant".to_string(),
                                content: response.content,
                            });
                        }
                        Err(e) => {
                            println!("\n❌ Sorry, I encountered an error: {}", e);
                            println!();
                            conversation.pop();
                        }
                    }
                } else {
                    // Use simple multi-model router (backward compatibility)
                    match router.chat(conversation.clone()).await {
                        Ok(response) => {
                            println!("{}", response.content);
                            println!("\n   [Model: {} | {}ms | Complexity: {:?}]", 
                                response.model_used,
                                response.latency.as_millis(),
                                response.complexity
                            );
                            println!();
                            
                            // Add assistant response to conversation
                            conversation.push(ChatMessage {
                                role: "assistant".to_string(),
                                content: response.content,
                            });
                        }
                        Err(e) => {
                            println!("\n❌ Sorry, I encountered an error: {}", e);
                            println!("   Make sure Ollama is running and models are available.");
                            println!();
                            conversation.pop();
                        }
                    }
                }
            }
        }
    }
}
