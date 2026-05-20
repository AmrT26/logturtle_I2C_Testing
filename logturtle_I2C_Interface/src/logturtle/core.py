import serial
import serial.tools.list_ports
import time
import sys
import webbrowser


BAUD_RATE = 115200

GITHUB_EXCEL_URL = "https://github.com/AmrT26/logturtle_I2C_Testing/blob/main/Reg%20Map.xlsx"

COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"

teensy = None
verbose_mode = False

history_registers = {}

VALID_REGISTERS = list(range(0, 8)) + list(range(16, 29))

DEFAULT_REG_VALUES = {
    0: 0b00000000,
    1: 0b10010000,
    2: 0b10100000,
    3: 0b00010100,
    4: 0b00100000,
    5: 0b00100000,
    6: 0b00000000,
    7: 0b00110000,
    # not needed for now
    16: 0b00100000,
    17: 0b00010000,
    18: 0b11111111,
    19: 0b00000000,
    20: 0b00011011,
    21: 0b00000000,
    22: 0b00000000,
    23: 0b01001100,
    24: 0b00100000,
    25: 0b00000000,
    26: 0b00000100,
    27: 0b00000000,
    28: 0b00000000
}

current_reg_states = DEFAULT_REG_VALUES.copy()

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


def get_universal_input(prompt_message, default_value=None):
    while True:
        user_input = input(prompt_message).strip()
        if not user_input and default_value is not None:
            return parse_any_base(default_value)
        if not user_input:
            print("[!] Empty input. Try again.")
            continue
        parsed = parse_any_base(user_input)
        if parsed is not None:
            return parsed


def format_binary_with_colors(current_val, default_val):
    bin_current = f"{current_val:08b}"
    bin_default = f"{default_val:08b}"

    formatted_chars = []
    for i in range(8):
        if i == 4:
            formatted_chars.append(" ")

        if bin_current[i] != bin_default[i]:
            formatted_chars.append(f"{COLOR_RED}{bin_current[i]}{COLOR_RESET}")
        else:
            formatted_chars.append(bin_current[i])

    return "".join(formatted_chars)


def process_teensy_output(device, is_read_operation=False):
    time.sleep(0.15)
    lines = []

    while device.in_waiting > 0:
        line = device.readline().decode('utf-8', errors='ignore').strip()
        if line:
            if "[i2c write]" in line.lower() or "[i2c read]" in line.lower():
                continue
            lines.append(line)
            if verbose_mode:
                print(f"  {line}")

    if not verbose_mode:
        output_str = " ".join(lines).lower()

        if "nack" in output_str or "failed" in output_str:
            print(f"  -> {COLOR_RED}NACK / FAIL{COLOR_RESET}")
            return None

        if is_read_operation and "data:" in output_str:
            parts = output_str.split("data:")
            if len(parts) > 1:
                after_data = parts[1].replace(",", " ").replace(";", " ").replace(":", " ").split()
                for word in after_data:
                    if word.startswith("0x"):
                        try:
                            val_int = int(word, 16)
                            print(f"  -> ACK | Data read: 0x{val_int:02x} ({val_int:08b})")
                            return f"0x{val_int:02x}"
                        except ValueError:
                            pass
            print("  -> ACK | Success (No data extracted)")
            return "0x00"

        else:
            print("  -> ACK | Success")
            return "0x00"

    return "0x00"


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

    process_teensy_output(teensy, is_read_operation=False)

    reg_int = int(hex_reg, 16)
    data_int = int(hex_data, 16)

    if reg_int in VALID_REGISTERS:
        current_reg_states[reg_int] = data_int
        history_registers[reg_int] = (hex_reg, hex_data)
    return True


def i2c_read(addr, reg):
    global teensy, current_reg_states
    hex_addr = parse_any_base(addr)
    hex_reg = parse_any_base(reg)

    if not (hex_addr and hex_reg):
        print("[!] Read operation failed: invalid parameters.")
        return

    if verbose_mode:
        print(f"\n[I2C READ] Chip: {hex_addr} | Reg: {hex_reg}")

    teensy.write(f"a {hex_addr}\n".encode('utf-8'))
    time.sleep(0.02)
    teensy.write(f"r {hex_reg}\n".encode('utf-8'))

    res = process_teensy_output(teensy, is_read_operation=True)

    if res and res.startswith("0x"):
        reg_int = int(hex_reg, 16)
        if reg_int in VALID_REGISTERS:
            current_reg_states[reg_int] = int(res, 16)
    return res

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


def read_and_display_all_map(chip_addr="0x20"):
    global verbose_mode
    print("\n" + "=" * 60)
    print(f" READING REGISTER MAP FROM CHIP {chip_addr} (Plages 0-7, 16-28)")
    print("=" * 60)

    old_verbose = verbose_mode
    verbose_mode = False

    for reg in VALID_REGISTERS:
        print(f"  Reg {reg:<2} (0x{reg:02x}) : ", end="")
        sys.stdout.flush()
        i2c_read(chip_addr, hex(reg))
        time.sleep(0.02)

    verbose_mode = old_verbose
    print("=" * 60)


def dump_register_map():
    print("\n" + "=" * 50)
    print(" d - Dump Formatting")
    print("=" * 50)
    print(f"  {'Reg':<10} | {'Data (Binary)':<20}")
    print("-" * 50)

    for reg in VALID_REGISTERS:
        current_val = current_reg_states[reg]
        default_val = DEFAULT_REG_VALUES[reg]

        # Formatage binaire couleur bit à bit
        binary_str = format_binary_with_colors(current_val, default_val)
        print(f"  {reg:<10} | {binary_str}")
    print("=" * 50)


def clear_history_and_states():
    global history_registers, current_reg_states
    history_registers.clear()
    current_reg_states = DEFAULT_REG_VALUES.copy()
    print(f"\n[OK] History cleared. All registers reset to their default values.")

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
    print("  [g] -> Last input")
    print("  [s] -> Scaning the I2C bus")
    print("  [v] -> Toggle VERBOSE mode")
    print("  [r] -> READ a register")
    print("  [w] -> WRITE in a register")
    print("  [o] -> OPEN Excel Register Map (GitHub)")
    print("  [rm]-> READ the REGISTER MAP on the chip")
    print("  [t] -> LAUNCH test_anatest()")
    print("  [d] -> DUMP register map")
    print("  [h] -> View the HISTORY of written registers")
    print("  [ch]-> CLEAR HISTORY")
    print("  [q] -> Quit the application")
    print("-" * 40)


def main():
    global teensy, verbose_mode
    teensy = connect_to_teensy()
    read_all_from_teensy(teensy)

    last_action = {
        "choice": None,
        "addr": None,
        "reg": None,
        "data": None
    }

    while True:
        print_user_menu()
        choice = input("Choose an action : ").strip().lower()

        if choice == 'g':
            if last_action["choice"] is None:
                print("\n[!] No action has been performed yet during this session.")
                continue

            prev_choice = last_action["choice"]

            if prev_choice == 'r':
                print(f"\n[REPEAT] Quick READ -> Chip: {last_action['addr']} | Reg: {last_action['reg']}")
                i2c_read(last_action["addr"], last_action["reg"])
                continue

            elif prev_choice == 'w':
                print(
                    f"\n[REPEAT] Quick WRITE -> Chip: {last_action['addr']} | Reg: {last_action['reg']} | Data: {last_action['data']}")
                i2c_write(last_action["addr"], last_action["reg"], last_action["data"])
                continue

            else:
                print(f"\n[REPEAT] Re-executing action... (Choice: [{prev_choice}])")
                choice = prev_choice

        if choice in ['s', 'v', 'r', 'w', 'o', 'rm', 't', 'd', 'h', 'ch']:
            if choice not in ['r', 'w', 'rm']:
                last_action["choice"] = choice

        if choice == 's':
            print("\n[Action] Complete Scan of the I2C bus...")
            teensy.write(b's\n')
            read_all_from_teensy(teensy)

        elif choice == 'v':
            verbose_mode = not verbose_mode
            print(f"\n[INFO] Verbose mode toggled. Now it is {'ON' if verbose_mode else 'OFF'}.")

        elif choice == 'r':
            print("\n--- READING CONFIGURATION ---")
            print("(Accepted formats : Hexa '0x40', Binaire '0b0010', Décimal '64')")
            addr = get_universal_input("1. Chip Address (ex: 0x20) [Default: 0x20 - Press Enter]: ", default_value='0x20')
            reg = get_universal_input("2. Register number (ex: 0x02) : ")
            last_action = {"choice": 'r', "addr": addr, "reg": reg, "data": None}
            i2c_read(addr, reg)

        elif choice == 'w':
            print("\n--- WRITING CONFIGURATION ---")
            print("(Accepted formats : Hexa '0x20', Binaire '0b0010', Décimal '64')")
            addr = get_universal_input("1. Chip Address (ex: 0x20) [Default: 0x20 - Press Enter]: ", default_value='0x20')
            reg = get_universal_input("2. Register number (ex: 0x00) : ")
            data = get_universal_input("3. Data value (ex: 0xAB) : ")
            last_action = {"choice": 'w', "addr": addr, "reg": reg, "data": data}
            i2c_write(addr, reg, data)

        elif choice == 'o':
            open_excel_on_github()

        elif choice == 'rm':
            addr = get_universal_input("Chip target [Default: 0x20 - Press Enter]: ", default_value="0x20")
            read_and_display_all_map(addr)
            last_action = {"choice": 'rm', "addr": addr, "reg": None, "data": None}

        elif choice == 't':
            test_anatest()

        elif choice == 'd':
            dump_register_map()

        elif choice == 'h':
            show_write_history()

        elif choice == 'ch':
            clear_history_and_states()

        elif choice == 'q':
            print("\nClosing the interface. Session ended.")
            teensy.close()
            break
        else:
            print("\n[!] invalid Option. Select 1, 2, 3, 4 ou Q.")


if __name__ == "__main__":
    main()