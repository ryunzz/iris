/*
  Iris Smart Glasses - Arduino Nano OLED Display
  
  Receives display data from Python main.py via Serial (9600 baud)
  Format: "line1|line2|line3|line4\n"
  Displays 4 lines of text on 128x64 OLED display
  
  Hardware:
  - Arduino Nano
  - 128x64 OLED display (SSD1306) on I2C
  - Connect OLED VCC to 3.3V or 5V
  - Connect OLED GND to GND  
  - Connect OLED SDA to A4
  - Connect OLED SCL to A5
  
  Libraries needed:
  - Adafruit SSD1306
  - Adafruit GFX Library
  
  Install via Arduino IDE: Tools > Manage Libraries > Search for "SSD1306"
*/

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// OLED display configuration
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1      // Reset pin (not used)
#define SCREEN_ADDRESS 0x3C // I2C address (try 0x3D if 0x3C doesn't work)

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

void setup() {
  // Initialize serial communication at 9600 baud
  Serial.begin(9600);
  
  // Initialize OLED display
  if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    // If display init fails, send error to serial
    Serial.println("ERROR: OLED display init failed!");
    for(;;); // Infinite loop on error
  }
  
  // Clear display and set text parameters
  display.clearDisplay();
  display.setTextSize(1);        // Small text (6x8 pixels per character)
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  
  // Show startup message
  display.println("Iris Smart Glasses");
  display.println("Nano Display Ready");
  display.println("Waiting for data...");
  display.display();
  
  // Send ready signal to Python
  Serial.println("NANO_DISPLAY_READY");
}

void loop() {
  // Check if data is available on serial
  if (Serial.available()) {
    // Read line until newline character
    String data = Serial.readStringUntil('\n');
    data.trim(); // Remove any whitespace
    
    if (data.length() > 0) {
      // Parse and display the data
      displayLines(data);
    }
  }
}

void displayLines(String data) {
  // Clear the display
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  
  // Split data by "|" character and display up to 4 lines
  int lineCount = 0;
  int startIndex = 0;
  
  for (int i = 0; i <= data.length() && lineCount < 4; i++) {
    // Check for delimiter or end of string
    if (i == data.length() || data.charAt(i) == '|') {
      // Extract line text
      String line = data.substring(startIndex, i);
      
      // Calculate y position (16 pixels per line for 4 lines)
      int y = lineCount * 16;
      
      // Set cursor and print line
      display.setCursor(0, y);
      
      // Truncate line if too long (max ~21 characters at size 1)
      if (line.length() > 21) {
        line = line.substring(0, 18) + "...";
      }
      
      display.println(line);
      
      lineCount++;
      startIndex = i + 1;
    }
  }
  
  // Update the display
  display.display();
  
  // Send confirmation back to Python (optional debug)
  Serial.print("DISPLAYED: ");
  Serial.println(data);
}