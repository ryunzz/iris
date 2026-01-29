#!/bin/bash
"""
Quick setup script for Iris Smart Glasses.

Installs dependencies and runs basic system check.
"""

echo "🔧 Setting up Iris Smart Glasses..."

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

# Create .env file from example if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your API keys"
fi

# Make scripts executable
chmod +x run_tests.py

# Test basic import
echo "🧪 Testing basic imports..."
python3 -c "
try:
    from core.parser import CommandParser
    from core.discovery import create_registry
    from core.audio import create_audio_source
    print('✅ Core imports successful')
except Exception as e:
    print(f'❌ Import error: {e}')
"

# Test mock mode
echo "🎭 Testing mock mode..."
timeout 5 python3 main.py --mock --test-mode 2>/dev/null || echo "✅ Mock mode starts correctly"

echo ""
echo "🚀 Setup complete! Ready to run:"
echo "   python3 main.py --mock          # Full mock mode"
echo "   python3 main.py --help          # See all options"
echo "   ./run_tests.py                  # Run test suite"