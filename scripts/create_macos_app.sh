#!/bin/bash
# AGENT_GURU macOS .app Bundle Creator

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Agent Guru macOS App Bundle Creator                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if release binary exists
if [ ! -f "target/release/agent_guru_voice" ]; then
    echo "❌ Release binary not found!"
    echo "   Run: cargo build --release --bin agent_guru_voice"
    exit 1
fi

echo "✅ Release binary found"
echo ""

# Create app bundle structure
APP_NAME="Agent Guru"
APP_DIR="installers/macos/${APP_NAME}.app"
CONTENTS_DIR="${APP_DIR}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"
RESOURCES_DIR="${CONTENTS_DIR}/Resources"

echo "📁 Creating app bundle structure..."
mkdir -p "${MACOS_DIR}"
mkdir -p "${RESOURCES_DIR}"
mkdir -p "${RESOURCES_DIR}/config"
mkdir -p "${RESOURCES_DIR}/scripts"

# Copy binary
echo "📋 Copying binary..."
cp target/release/agent_guru_voice "${MACOS_DIR}/Agent Guru"
chmod +x "${MACOS_DIR}/Agent Guru"

# Copy logo
echo "🎨 Adding app icon..."
if [ -f "assets/logo.png" ]; then
    mkdir -p "${RESOURCES_DIR}/icon.iconset"
    # Create different icon sizes for macOS
    sips -z 16 16     assets/logo.png --out "${RESOURCES_DIR}/icon.iconset/icon_16x16.png"
    sips -z 32 32     assets/logo.png --out "${RESOURCES_DIR}/icon.iconset/icon_16x16@2x.png"
    sips -z 32 32     assets/logo.png --out "${RESOURCES_DIR}/icon.iconset/icon_32x32.png"
    sips -z 64 64     assets/logo.png --out "${RESOURCES_DIR}/icon.iconset/icon_32x32@2x.png"
    sips -z 128 128   assets/logo.png --out "${RESOURCES_DIR}/icon.iconset/icon_128x128.png"
    sips -z 256 256   assets/logo.png --out "${RESOURCES_DIR}/icon.iconset/icon_128x128@2x.png"
    sips -z 256 256   assets/logo.png --out "${RESOURCES_DIR}/icon.iconset/icon_256x256.png"
    sips -z 512 512   assets/logo.png --out "${RESOURCES_DIR}/icon.iconset/icon_256x256@2x.png"
    sips -z 512 512   assets/logo.png --out "${RESOURCES_DIR}/icon.iconset/icon_512x512.png"
    sips -z 1024 1024 assets/logo.png --out "${RESOURCES_DIR}/icon.iconset/icon_512x512@2x.png"
    
    # Convert to icns
    iconutil -c icns "${RESOURCES_DIR}/icon.iconset" -o "${RESOURCES_DIR}/icon.icns"
    rm -rf "${RESOURCES_DIR}/icon.iconset"
    echo "✅ App icon created"
else
    echo "⚠️  Logo not found at assets/logo.png"
fi

# Copy configuration
echo "📋 Copying configuration..."
if [ -f ".kiro/llm_config.yaml" ]; then
    cp .kiro/llm_config.yaml "${RESOURCES_DIR}/config/"
fi

# Create Info.plist
echo "📝 Creating Info.plist..."
cat > "${CONTENTS_DIR}/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>Agent Guru</string>
    <key>CFBundleIdentifier</key>
    <string>com.agentguru.voice</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Agent Guru</string>
    <key>CFBundleDisplayName</key>
    <string>Agent Guru</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>CFBundleIconFile</key>
    <string>icon.icns</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>AGENT_GURU needs microphone access for voice interaction</string>
    <key>NSSpeechRecognitionUsageDescription</key>
    <string>AGENT_GURU uses speech recognition for voice commands</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

# Create post-installation setup script
echo "📝 Creating post-installation setup script..."
cat > "${RESOURCES_DIR}/scripts/setup.sh" << 'EOF'
#!/bin/bash
# Agent Guru Post-Installation Setup for macOS

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Agent Guru Post-Installation Setup                    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Welcome to Agent Guru! Let's get you set up."
echo ""
echo "Agent Guru can work in two modes:"
echo "  1. LOCAL MODE  - Uses Ollama (private, offline)"
echo "  2. CLOUD MODE  - Uses OpenAI or Gemini APIs"
echo ""
read -p "Choose your mode (1 or 2): " mode_choice

if [ "$mode_choice" = "1" ]; then
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "LOCAL MODE SETUP"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "Step 1: Install Ollama"
    echo ""
    
    if ! command -v ollama &> /dev/null; then
        echo "Ollama is not installed. Installing via Homebrew..."
        
        if ! command -v brew &> /dev/null; then
            echo "Homebrew not found. Installing Homebrew first..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        
        brew install ollama
    fi
    
    echo "✅ Ollama is installed"
    echo ""
    echo "Step 2: Download AI Models"
    echo ""
    echo "Downloading models (this may take a few minutes)..."
    
    # Start Ollama service in background
    ollama serve &
    OLLAMA_PID=$!
    sleep 3
    
    ollama pull mistral:7b-instruct
    ollama pull qwen2.5:14b-instruct
    
    echo ""
    echo "✅ Models downloaded successfully"
    echo ""
    echo "Step 3: Ollama Service"
    echo ""
    echo "Ollama will start automatically when needed."
    echo "To manually start: ollama serve"
    
elif [ "$mode_choice" = "2" ]; then
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "CLOUD MODE SETUP"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "You'll need API keys from OpenAI or Google Gemini."
    echo ""
    echo "Choose your provider:"
    echo "  1. OpenAI (ChatGPT)"
    echo "  2. Google Gemini"
    echo "  3. Both"
    echo ""
    read -p "Select provider (1, 2, or 3): " provider_choice
    
    if [ "$provider_choice" = "1" ] || [ "$provider_choice" = "3" ]; then
        echo ""
        echo "OpenAI Setup:"
        echo "  1. Go to: https://platform.openai.com/api-keys"
        echo "  2. Create a new API key"
        echo "  3. Copy the key"
        echo ""
        read -p "Paste your OpenAI API key: " openai_key
        
        # Add to shell profile
        echo "export OPENAI_API_KEY=\"$openai_key\"" >> ~/.zshrc
        echo "export OPENAI_API_KEY=\"$openai_key\"" >> ~/.bash_profile
        export OPENAI_API_KEY="$openai_key"
        
        echo "✅ OpenAI API key saved"
    fi
    
    if [ "$provider_choice" = "2" ] || [ "$provider_choice" = "3" ]; then
        echo ""
        echo "Google Gemini Setup:"
        echo "  1. Go to: https://makersuite.google.com/app/apikey"
        echo "  2. Create a new API key"
        echo "  3. Copy the key"
        echo ""
        read -p "Paste your Gemini API key: " gemini_key
        
        # Add to shell profile
        echo "export GEMINI_API_KEY=\"$gemini_key\"" >> ~/.zshrc
        echo "export GEMINI_API_KEY=\"$gemini_key\"" >> ~/.bash_profile
        export GEMINI_API_KEY="$gemini_key"
        
        echo "✅ Gemini API key saved"
    fi
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Setup Complete!                                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Agent Guru is ready to use!"
echo ""
echo "To start Agent Guru:"
echo "  1. Open the Agent Guru app from Applications"
echo "  2. Or run from Terminal: /Applications/Agent\ Guru.app/Contents/MacOS/Agent\ Guru"
echo "  3. Say 'Hey Guru' or 'Hey Maya' to start talking!"
echo ""
echo "For help: AGENT_GURU --help"
echo ""
read -p "Press Enter to continue..."
EOF

chmod +x "${RESOURCES_DIR}/scripts/setup.sh"

# Create launcher script that runs setup on first launch
echo "📝 Creating launcher wrapper..."
cat > "${MACOS_DIR}/${APP_NAME}_launcher" << 'EOF'
#!/bin/bash
# Agent Guru Launcher with first-run setup

SETUP_FLAG="$HOME/.kiro/.setup_complete"

if [ ! -f "$SETUP_FLAG" ]; then
    # First run - open Terminal and run setup
    osascript -e 'tell application "Terminal" to do script "'"$(dirname "$0")/../Resources/scripts/setup.sh"'"'
    
    # Wait for setup to complete
    while [ ! -f "$SETUP_FLAG" ]; do
        sleep 1
    done
fi

# Run Agent Guru
"$(dirname "$0")/Agent Guru"
EOF

chmod +x "${MACOS_DIR}/${APP_NAME}_launcher"

# Update Info.plist to use launcher
sed -i '' 's/<string>Agent Guru<\/string>/<string>Agent Guru_launcher<\/string>/' "${CONTENTS_DIR}/Info.plist"

# Create README
echo "📝 Creating README..."
cat > "${RESOURCES_DIR}/README.txt" << 'EOF'
Agent Guru - Voice-Driven AI Companion
========================================

Installation Instructions:

1. Copy Agent Guru.app to your Applications folder
2. Double-click to launch (setup will run on first launch)
3. Follow the on-screen setup instructions
4. Start talking to Agent Guru!

Voice Commands:
- Say "Hey Guru" or "Hey Maya" to wake up
- Speak naturally to interact
- Say "Stop listening" to pause
- Say "Exit" or "Goodbye" to quit

Configuration:
- Config file: ~/.kiro/llm_config.yaml
- Logs: ~/.kiro/logs/

Support:
- Documentation: https://github.com/Surajsharma0804/Agent_Guru
- Issues: https://github.com/Surajsharma0804/Agent_Guru/issues

EOF

# Create DMG installer (optional)
echo ""
echo "📦 Creating DMG installer..."
if command -v create-dmg &> /dev/null; then
    create-dmg \
        --volname "Agent Guru Installer" \
        --window-pos 200 120 \
        --window-size 800 400 \
        --icon-size 100 \
        --icon "Agent Guru.app" 200 190 \
        --hide-extension "Agent Guru.app" \
        --app-drop-link 600 185 \
        "installers/macos/Agent_Guru-Installer.dmg" \
        "${APP_DIR}"
    
    echo "✅ DMG installer created: installers/macos/Agent_Guru-Installer.dmg"
else
    echo "⚠️  create-dmg not found. Skipping DMG creation."
    echo "   Install with: brew install create-dmg"
fi

echo ""
echo "✅ macOS app bundle created!"
echo "📦 Location: ${APP_DIR}"
echo ""
echo "To distribute:"
echo "  1. Copy ${APP_DIR} to a USB drive or cloud storage"
echo "  2. Or create a DMG: hdiutil create -volname Agent_Guru -srcfolder ${APP_DIR} -ov -format UDZO installers/macos/Agent_Guru.dmg"
echo "  3. Users drag to Applications folder and launch"
echo ""
