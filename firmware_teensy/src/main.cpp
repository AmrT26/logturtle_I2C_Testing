#include <Arduino.h>

// ============================================
// LOGTURTLE - I2C
// Comparator only on SDA 
// SDA inverted, SCL normal
// ============================================

const int SDA_PIN = 18;
const int SCL_PIN = 19;
const int ADC_PIN = 14; // Pin 14 Teensy 4.1
const int PIN_TEST = 12;
const int HALF_PERIOD_US = 250; // 2kHz

byte current_address = 0x20;
byte current_reg     = 0x00;
byte current_data    = 0xAB;

// ============================================
// IOMUX
// ============================================

void config_pins_iomux() {
  // SDA Pin 18 → Push-Pull (ODE=0)
  IOMUXC_SW_PAD_CTL_PAD_GPIO_AD_B1_01 &= ~(1 << 11);
  // SCL Pin 19 → Open-Drain (ODE=1)
  IOMUXC_SW_PAD_CTL_PAD_GPIO_AD_B1_00 |=  (1 << 11);
}

// ============================================
// SDA — INVERTED (comparator on SDA)
// ============================================

void sda_high() {
  // We want the chip to see HIGH
  // Inverted comparator
  // → We send LOW to the comparator
  pinMode(SDA_PIN, OUTPUT);
  digitalWrite(SDA_PIN, LOW);
}

void sda_low() {
  // We want the chip to see LOW
  // Inverted comparator
  // → We send HIGH to the comparator
  // → We release the pin (pull-up → HIGH)
  pinMode(SDA_PIN, INPUT);
}

int read_sda() {
  // The chip sends a bit on SDA
  // The comparator inverts it before we read it
  // → We invert what we read
  pinMode(SDA_PIN, INPUT);
  int raw = digitalRead(SDA_PIN);
  return 1 - raw; // compensation inversion
}

// ============================================
// SCL — NORMAL
// ============================================

void scl_high() {
  pinMode(SCL_PIN, INPUT);
  delayMicroseconds(HALF_PERIOD_US);
}

// New version of scl_high() without delay
void scl_high_no_delay() {
  pinMode(SCL_PIN, INPUT);
  // No delay here
}

void scl_low() {
  pinMode(SCL_PIN, OUTPUT);
  digitalWrite(SCL_PIN, LOW);
  delayMicroseconds(HALF_PERIOD_US);
}

// ============================================
// START
// SDA falls while SCL HIGH
// With SDA inversion:
// → sda_low() makes SDA go high on chip side
// → sda_high() makes SDA go low on chip side
// ============================================

void i2c_start() {
  // Idle state: SDA HIGH, SCL HIGH
  sda_high(); // chip sees HIGH
  scl_high(); // normal
  delayMicroseconds(HALF_PERIOD_US);

  // START: SDA falls while SCL HIGH
  sda_low();  // chip sees LOW = START
  delayMicroseconds(HALF_PERIOD_US);

  scl_low();  // SCL falls after SDA
  delayMicroseconds(HALF_PERIOD_US);

  Serial.println("START");
}

// ============================================
// STOP
// SDA rises while SCL HIGH
// ============================================

void i2c_stop() {
  sda_low();  // chip sees LOW
  scl_high(); // SCL rises
  delayMicroseconds(HALF_PERIOD_US);

  sda_high(); // chip voit HIGH = STOP
  delayMicroseconds(HALF_PERIOD_US);

  Serial.println("STOP");
}

// ============================================
// WRITE A BIT
// SCL normal, SDA inverted
// ============================================

void i2c_write_bit(int bit) {
  // SCL low → prepare SDA
  scl_low();

  // Set SDA according to the desired bit
  // The sda_high/low functions handle
  // the inversion automatically
  if(bit) {
    sda_high(); // chip voit 1 
  } else {
    sda_low();  // chip voit 0 
  }

  delayMicroseconds(HALF_PERIOD_US);

  // SCL high → chip reads SDA
  scl_high();

  // SCL low → end of the bit
  scl_low();
}

// ============================================
// READ A BIT (ACK/NACK)
// ============================================

/*
int i2c_read_bit() {
  scl_low();
  sda_high(); // release SDA (chip can write)
  delayMicroseconds(HALF_PERIOD_US);

  scl_high(); // chip writes on SDA

  // read_sda() handles the inversion
  int bit = read_sda(); 

  scl_low();
  return bit;
}
*/

int read_adc() {
  const int THRESHOLD_HIGH = 520; // 10 bits resolution here
  //pinMode(PIN_TEST, OUTPUT);
  digitalWrite(PIN_TEST, HIGH);
  int raw = analogRead(ADC_PIN);
  digitalWrite(PIN_TEST, LOW);
  Serial.print("ADC raw: ");
  Serial.println(raw);
  if(raw > THRESHOLD_HIGH) {
    return 0; // chip sees LOW
  } else {
    return 1; // chip sees HIGH
  }
}



int i2c_read_adc() {
  scl_low();
  sda_high(); // release SDA (chip can write)
  delayMicroseconds(50); // Small delay for SDA to settle

  scl_high_no_delay(); // chip writes on SDA (no internal delay)

  delayMicroseconds(50); // Short delay for ACK to settle on SDA

  // read_sda() handles the inversion
  int bit = read_adc(); 

  delayMicroseconds(HALF_PERIOD_US - 50); // Complete the full clock period

  scl_low();
  return bit;
}


// ============================================
// WRITE A BYTE
// ============================================

void i2c_write_byte(byte data) {
  Serial.print("  TX: 0x");
  Serial.print(data, HEX);
  Serial.print(" (0b");
  Serial.print(data, BIN);
  Serial.println(")");

  for(int i = 7; i >= 0; i--) {
    int bit = (data >> i) & 0x01;
    i2c_write_bit(bit);
  }
}

// ============================================
// READ A BYTE
// ============================================

byte i2c_read_byte() {
  byte data = 0;
  for(int i = 7; i >= 0; i--) {
    int bit = i2c_read_adc();
    data |= (bit << i);
  }
  return data;
}

// ============================================
// ACK / NACK
// ============================================

bool i2c_read_ack() {
  int ack = i2c_read_adc();
  Serial.print("  raw ack bit: ");
  Serial.println(ack);
  if(ack == 0) {
    Serial.println("  → ACK");
    return true;
  } else {
    Serial.println("  → NACK");
    return false;
  }
}

void i2c_send_nack() {
  i2c_write_bit(1); // NACK = 1
}

// ============================================
// WRITE REGISTER
// START | addr+W | reg | data | STOP
// ============================================

void i2c_write_register(byte address,
                        byte reg,
                        byte data) {
  Serial.println("==============================");
  Serial.println(" WRITE");
  Serial.print  (" Addr: 0x"); Serial.println(address, HEX);
  Serial.print  (" Reg : 0x"); Serial.println(reg, HEX);
  Serial.print  (" Data: 0x"); Serial.println(data, HEX);
  Serial.println("------------------------------");

  i2c_start();

  // Adresse + W=0
  byte addr_w = (address << 1) | 0x00;
  Serial.print(" addr+W: 0x");
  Serial.println(addr_w, HEX);
  i2c_write_byte(addr_w);
  bool ack1 = i2c_read_ack();

  if(!ack1) {
    Serial.println(" Failed at address !");
    i2c_stop();
    return;
  }

  // Register
  i2c_write_byte(reg);
  bool ack2 = i2c_read_ack();

  if(!ack2) {
    Serial.println(" Failed at register !");
    i2c_stop();
    return;
  }

  // Data
  i2c_write_byte(data);
  i2c_read_ack();

  i2c_stop();
  Serial.println("==============================");
}

// ============================================
// READ REGISTER
// START|addr+W|reg|RESTART|addr+R|data|STOP
// ============================================

void i2c_read_register(byte address, byte reg) {
  Serial.println("==============================");
  Serial.println(" READ");
  Serial.print  (" Addr: 0x"); Serial.println(address, HEX);
  Serial.print  (" Reg : 0x"); Serial.println(reg, HEX);
  Serial.println("------------------------------");

  // Phase 1 : Write register index
  i2c_start();

  byte addr_w = (address << 1) | 0x00;
  i2c_write_byte(addr_w);
  bool ack1 = i2c_read_ack();

  if(!ack1) {
    Serial.println(" Failed at address !");
    i2c_stop();
    return;
  }

  i2c_write_byte(reg);
  i2c_read_ack();

  // Phase 2 : Read data
  Serial.println(" RESTART");
  i2c_start(); // RESTART

  byte addr_r = (address << 1) | 0x01;
  i2c_write_byte(addr_r);
  bool ack2 = i2c_read_ack();

  if(!ack2) {
    Serial.println(" Failed at read address !");
    i2c_stop();
    return;
  }

  // Read the data
  byte data = i2c_read_byte();
  i2c_send_nack(); // tell the chip to stop

  Serial.print(" Data: 0x");
  Serial.print(data, HEX);
  Serial.print(" (0b");
  Serial.print(data, BIN);
  Serial.println(")");

  i2c_stop();
  Serial.println("==============================");
}

// ============================================
// SCAN BUS
// ============================================

void scanBus() {
  Serial.println("=== Scanning I2C bus ===");
  int found = 0;
  // Iterate all possible I2C addresses (1 to 126)
  for(byte addr = 1; addr < 127; addr++) {
    i2c_start();                      // Start of I2C frame
    byte addr_w = (addr << 1) | 0x00; // Address + R/W bit = 0 (write)
    i2c_write_byte(addr_w);           // Send the address on the bus
    bool ack = i2c_read_ack();        // Check if a device responded ACK
    i2c_stop();                       // End of the I2C frame

    if(ack) {
      Serial.print("  Found: 0x");
      if(addr < 16) Serial.print("0");// Add a leading 0 for neat display
      Serial.println(addr, HEX);      // Display the found device address in hex
      found++;
    }
  }

  if(found == 0) {
    Serial.println("  No devices found"); // No device found on the bus
  }
  Serial.println("========================");
}

// ============================================
// PARSE HEX
// ============================================

byte parseHex(String str) {
  str.trim();
  if(str.startsWith("0x") || str.startsWith("0X")) {
    str = str.substring(2);
  }
  return (byte)strtol(str.c_str(), NULL, 16);
}

// ============================================
// MENU
// ============================================

void printMenu() {
  Serial.println("==============================");
  Serial.println(" LOGTURTLE I2C Controller");
  Serial.println(" SDA inverted (comparator)");
  Serial.println(" SCL normal");
  Serial.println(" Clock : 2kHz");
  Serial.println("==============================");
  Serial.print  (" Address : 0x");
  Serial.println(current_address, HEX);
  Serial.print  (" Register: 0x");
  Serial.println(current_reg, HEX);
  Serial.print  (" Data    : 0x");
  Serial.println(current_data, HEX);
  Serial.println("------------------------------");
  Serial.println(" Commands:");
  Serial.println("   a 0x40 → Set address");
  Serial.println("   i 0x00 → Set register");
  Serial.println("   d 0xAB → Set data");
  Serial.println("   w      → Write register");
  Serial.println("   r      → Read register");
  Serial.println("   s      → Scan bus");
  Serial.println("   h      → Help");
  Serial.println("==============================");
}

// ============================================
// SETUP
// ============================================

void setup() {
  Serial.begin(115200);
  delay(1000);

  config_pins_iomux();

  // IDLE: SDA HIGH, SCL HIGH
  sda_high();
  scl_high();

  Serial.println("==============================");
  Serial.println(" Init OK");
  Serial.println(" SDA : inverted (comparator)");
  Serial.println(" SCL : normal");
  Serial.println("==============================");

  printMenu();
}

// ============================================
// LOOP
// ============================================

void loop() {
  if(Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    char cmd = input.charAt(0);
    String param = "";
    if(input.length() > 2) {
      param = input.substring(2);
    }

    switch(cmd) {
      case 'a':
        if(param.length() > 0) {
          current_address = parseHex(param);
          Serial.print("Address → 0x");
          Serial.println(current_address, HEX);
        } else {
          Serial.println("Usage: a 0x40");
        }
        break;

      case 'i':
        if(param.length() > 0) {
          current_reg = parseHex(param);
          Serial.print("Register → 0x");
          Serial.println(current_reg, HEX);
        } else {
          Serial.println("Usage: i 0x00");
        }
        break;

      case 'd':
        if(param.length() > 0) {
          current_data = parseHex(param);
          Serial.print("Data → 0x");
          Serial.print(current_data, HEX);
          Serial.print(" (0b");
          Serial.print(current_data, BIN);
          Serial.println(")");
        } else {
          Serial.println("Usage: d 0xAB");
        }
        break;

      case 'w':
        if(param.length() > 0) {
          current_data = parseHex(param);
        }
        i2c_write_register(current_address,
                           current_reg,
                           current_data);
        break;

      case 'r':
        if(param.length() > 0) {
          current_reg = parseHex(param);
        }
        i2c_read_register(current_address,
                          current_reg);
        break;

      case 's':
        scanBus();
        break;

      case 'h':
        printMenu();
        break;

      default:
        Serial.println("Unknown - type 'h' for help");
        break;
    }
  }
}