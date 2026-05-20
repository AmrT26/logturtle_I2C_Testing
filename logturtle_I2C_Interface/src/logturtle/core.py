import serial
import serial.tools.list_ports
import time
import sys
import webbrowser


BAUD_RATE = 115200

GITHUB_EXCEL_URL = "https://github.com/AmrT26/logturtle_I2C_Testing/blob/main/Reg%20Map.xlsx"

teensy = None

history_registers = {}


def find_teensy_port():
    print("[INFO] Automatic detection of the Teensy...")
    ports = list(serial.tools.list_ports.comports())

    for p in ports:
        description = str(p.description).lower()
        manufacturer = str(p.manufacturer).lower() if p.manufacturer else ""

        if "teensy" in description or "teensy" in manufacturer:
            print(f"[OK] Teensy detected on port: {p.device} ({p.description})")
            return p.device

    if ports:
        print(f"[WARNING] No device explicitly named 'Teensy' found.")
        print(f"[INFO] Multiple COM ports are active. Please select the correct one:")

        for index, p in enumerate(ports):
            print(f"  [{index}] -> {p.device} ({p.description})")

        while True:
            try:
                choice = input("Enter the number of your Teensy port: ").strip()
                choice_idx = int(choice)
                if 0 <= choice_idx < len(ports):
                    selected_port = ports[choice_idx].device
                    print(f"[INFO] Using selected port: {selected_port}")
                    return selected_port
                else:
                    print(f"[!] Invalid selection. Choose between 0 and {len(ports) - 1}")
            except ValueError:
                print("[!] Please enter a valid number.")

    print("[ERROR] No active COM ports detected. Is the Teensy plugged in?")
    return None

def parse_any_base(user_input):
    val_str = str(user_input).strip().lower()

    try:
        if val_str.startswith("0b"):
            val = int(val_str, 2)
        elif val_str.startswith("0x"):
            val = int(val_str, 16)
        elif len(val_str) == 8 and all(c in '01' for c in val_str):
            val = int(val_str, 2)
        elif any(c in 'abcdef' for c in val_str):
            val = int(val_str, 16)
        else:
            val = int(val_str, 10)

        if val < 0 or val > 255:
            raise ValueError("The value exceed 8 bits (0-255).")

        return f"0x{val:02x}"

    except ValueError as e:
        print(f"[!] Interpretation error of '{user_input}': {e}")
        return None


def get_universal_input(prompt_message):
    while True:
        user_input = input(prompt_message).strip()
        if not user_input:
            print("[!] Empty input. Try again.")
            continue
        parsed = parse_any_base(user_input)
        if parsed is not None:
            return parsed


def i2c_write(addr, reg, data):
    global teensy
    # Automatic conversion of inputs to the format required by the Teensy (‘0xXX’)
    hex_addr = parse_any_base(addr)
    hex_reg = parse_any_base(reg)
    hex_data = parse_any_base(data)

    if not (hex_addr and hex_reg and hex_data):
        print("[!] Write operation failed: invalid parameters.")
        return False

    print(f"\n[I2C WRITE] Chip: {hex_addr} | Reg: {hex_reg} | Data: {hex_data}")

    teensy.write(f"a {hex_addr}\n".encode('utf-8'))
    time.sleep(0.02)

    teensy.write(f"i {hex_reg}\n".encode('utf-8'))
    time.sleep(0.02)

    teensy.write(f"w {hex_data}\n".encode('utf-8'))

    read_all_from_teensy(teensy)

    reg_int = int(hex_reg, 16)
    history_registers[reg_int] = (hex_reg, hex_data)

    return True


def i2c_read(addr, reg):
    global teensy
    hex_addr = parse_any_base(addr)
    hex_reg = parse_any_base(reg)

    if not (hex_addr and hex_reg):
        print("[!] Read operation failed: invalid parameters.")
        return

    print(f"\n[I2C READ] Chip: {hex_addr} | Reg: {hex_reg}")

    teensy.write(f"a {hex_addr}\n".encode('utf-8'))
    time.sleep(0.02)
    teensy.write(f"r {hex_reg}\n".encode('utf-8'))

    read_all_from_teensy(teensy)

def show_write_history():
    print("\n" + "=" * 50)
    print("   HISTORY OF MODIFIED REGISTERS")
    print("=" * 50)

    if not history_registers:
        print("  [Pending] No entries have been made yet.")
        print("=" * 50)
        return

    print(f" {'Register':<12} | {'Last Data Written (Hexa)':<30}")
    print("-" * 50)

    sorted_registers = sorted(history_registers.keys())

    for reg_int in sorted_registers:
        hex_reg, hex_data = history_registers[reg_int]
        data_int = int(hex_data, 16)
        bin_data = f"0b{data_int:08b}"

        print(f"  {hex_reg:<10} | {hex_data}  ({bin_data})")

    print("=" * 50)

def test_anatest():
    print("\n" + "=" * 50)
    print(" AUTOMATIC TEST")
    print("=" * 50)

    print("\n--- TEST 1 : ---")
    i2c_write(0x20, 0, 0xFF)
    time.sleep(0.1)
    i2c_read(0x20, 0) # verification

    print("\n--- TEST 2 : ---")
    i2c_write(0x20, 3, "00110101")
    time.sleep(0.1)
    i2c_read(0x20, 3)  # verification

    print("\n" + "=" * 50)
    print(" END OF AUTOMATIC TEST")
    print("=" * 50)

def connect_to_teensy():
    actual_port = find_teensy_port()
    if not actual_port:
        print("[ERROR] Connection impossible : No COM port has been detected.")
    try:
        print(f"[INFO] Connection to Teensy on {actual_port}...")
        device = serial.Serial(actual_port, BAUD_RATE, timeout=1)
        time.sleep(2)
        print("[OK] Connected !\n")
        return device
    except serial.SerialException as e:
        print(f"[ERROR] Impossible to connect to the port {actual_port}.")
        print(f"Détails : {e}")
        sys.exit(1)


def read_all_from_teensy(device):
    time.sleep(0.15)
    while device.in_waiting > 0:
        line = device.readline().decode('utf-8', errors='ignore').strip()
        if line:
            print(f"  {line}")


def get_hexa_input(prompt_message):
    while True:
        user_input = input(prompt_message).strip().lower()
        if not user_input:
            print("[!] Entrée vide. Recommence.")
            continue
        if not user_input.startswith("0x"):
            user_input = "0x" + user_input
        try:
            int(user_input, 16)
            return user_input
        except ValueError:
            print("[!] invalid value. expecting : 0x40, 0x02...")


def open_excel_on_github():
    print(f"[INFO] Opening the Excel Register Map on the browser...")
    webbrowser.open(GITHUB_EXCEL_URL)


def print_user_menu():
    print("\n" + "=" * 40)
    print("      I2C INTERFACE")
    print("=" * 40)
    print("  [1] -> Scaning the I2C bus")
    print("  [2] -> READ a register")
    print("  [3] -> WRITE in a register")
    print("  [4] -> OPEN the register map")
    print("  [5] -> LAUNCH test_anatest()")
    print("  [6] -> View the HISTORY of written registers")
    print("  [Q] -> Quit the application")
    print("-" * 40)


def main():
    global teensy
    teensy = connect_to_teensy()
    read_all_from_teensy(teensy)

    while True:
        print_user_menu()
        choice = input("Choose an action : ").strip().lower()

        if choice == '1':
            print("\n[Action] Complete Scan of the I2C bus...")
            teensy.write(b's\n')
            read_all_from_teensy(teensy)

        elif choice == '2':
            print("\n--- READING CONFIGURATION ---")
            print("(Accepted formats : Hexa '0x40', Binaire '0b0010', Décimal '64')")
            addr = get_universal_input("1. Chip address (ex: 0x20) : ")
            reg = get_universal_input("2. Register number (ex: 0x02) : ")
            i2c_read(addr, reg)

        elif choice == '3':
            print("\n--- WRITING CONFIGURATION ---")
            print("(Accepted formats : Hexa '0x20', Binaire '0b0010', Décimal '64')")
            addr = get_universal_input("1. Chip Address (ex: 0x20) : ")
            reg = get_universal_input("2. Register number (ex: 0x00) : ")
            data = get_universal_input("3. Data value (ex: 0xAB) : ")
            i2c_write(addr, reg, data)

        elif choice == '4':
            open_excel_on_github()

        elif choice == '5':
            test_anatest()

        elif choice == '6':
            show_write_history()

        elif choice == 'q':
            print("\nClosing the interface. Session ended.")
            teensy.close()
            break
        else:
            print("\n[!] invalid Option. Select 1, 2, 3, 4 ou Q.")


if __name__ == "__main__":
    main()