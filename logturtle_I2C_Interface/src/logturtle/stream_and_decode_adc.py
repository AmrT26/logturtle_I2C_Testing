import ctypes
import sys
import time
import csv
import numpy as np
import pandas as pd
from scipy.signal import medfilt
import matplotlib.pyplot as plt
from dwfconstants import *

# --- DWF Library Loading ---
if sys.platform.startswith("win"):
    dwf = ctypes.cdll.dwf
elif sys.platform.startswith("darwin"):
    dwf = ctypes.cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")
else:
    dwf = ctypes.cdll.LoadLibrary("libdwf.so")

def save_raw_signals_to_csv(raw_samples, sample_period_ns, filename="raw_signals_capture.csv"):
    print(f"Exporting raw signals to {filename}...")
    try:
        with open(filename, mode='w', newline='') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["Time_ns", "DIO0_Data", "DIO1_Comp", "DIO2_Clock"])
            
            for idx, sample in enumerate(raw_samples):
                current_time_ns = idx * sample_period_ns
                bit0 = (sample >> 0) & 1  # DIO 0
                bit1 = (sample >> 1) & 1  # DIO 1
                bit2 = (sample >> 2) & 1  # DIO 2
                
                writer.writerow([f"{current_time_ns:.2f}", bit0, bit1, bit2])
        print("Raw signals CSV export complete.")
    except Exception as e:
        print(f"Error saving raw CSV: {e}")

def capture_data(duration_sec=1.0, SR=100000000.0, save_raw=True, raw_filename="raw_signals_capture.csv"):
    """
    Captures digital data streams from Digital Discovery.
    """
    hdwf = ctypes.c_int()
    sts = ctypes.c_ubyte()
    hzDI = ctypes.c_double()
    
    print("Opening Digital Discovery...")
    dwf.FDwfDeviceOpen(ctypes.c_int(-1), ctypes.byref(hdwf))
    if hdwf.value == 0:
        print("Error: Failed to open device.")
        return False

    # Disable auto-configuration to allow manual batch configuration
    dwf.FDwfDeviceAutoConfigureSet(hdwf, ctypes.c_int(0))
    
    # Query base internal clock frequency
    dwf.FDwfDigitalInInternalClockInfo(hdwf, ctypes.byref(hzDI))
    
    # Calculate the clock divider needed to match requested Sampling Rate (SR)
    divSample = int(round(hzDI.value / SR))
    actual_SR = hzDI.value / divSample
    sample_period_ns = 1e9 / actual_SR
    
    # Calculate total digital samples to collect
    total_samples_to_record = int(duration_sec * actual_SR)
    
    print(f"-> Base Internal Frequency: {hzDI.value / 1e6:.2f} MHz")
    print(f"-> Configured Divider: {divSample} (Actual SR: {actual_SR / 1e6:.2f} MHz)")
    print(f"-> Sample Period: {sample_period_ns:.2f} ns")
    print(f"-> Target Samples to Collect: {total_samples_to_record}")

    # --- Hardware Interface Configuration ---
    dwf.FDwfDigitalInAcquisitionModeSet(hdwf, acqmodeRecord)
    dwf.FDwfDigitalInDividerSet(hdwf, ctypes.c_int(divSample))
    dwf.FDwfDigitalInSampleFormatSet(hdwf, ctypes.c_int(8))  # 8-bit format (DIN0 to DIN7)
    dwf.FDwfDigitalInTriggerPositionSet(hdwf, ctypes.c_int(0))
    dwf.FDwfDigitalInTriggerSourceSet(hdwf, trigsrcNone)
    dwf.FDwfDigitalInInputOrderSet(hdwf, ctypes.c_int(0))

    # Start recording stream
    dwf.FDwfDigitalInConfigure(hdwf, ctypes.c_int(0), ctypes.c_int(1))
    print("Recording stream active...")

    raw_samples = []
    samples_collected = 0
    
    cAvailable = ctypes.c_int()
    cLost = ctypes.c_int()
    cCorrupted = ctypes.c_int()
    
    # --- Data Streaming Acquisition Loop ---
    try:
        while samples_collected < total_samples_to_record:
            if dwf.FDwfDigitalInStatus(hdwf, ctypes.c_int(1), ctypes.byref(sts)) == 0:
                print("Hardware Status Error.")
                break
                
            dwf.FDwfDigitalInStatusRecord(hdwf, ctypes.byref(cAvailable), ctypes.byref(cLost), ctypes.byref(cCorrupted))
            
            if cLost.value > 0:
                print(f"\n USB Buffer Overflow! Lost {cLost.value} samples. Lower your SR parameter.")
            
            if cAvailable.value > 0:
                # Avoid reading past our targeted sample size boundary
                chunk_size = min(cAvailable.value, total_samples_to_record - samples_collected)
                rgbBuffer = (ctypes.c_uint8 * chunk_size)()
                
                dwf.FDwfDigitalInStatusData(hdwf, ctypes.byref(rgbBuffer), ctypes.c_int(chunk_size))
                
                # Append raw binary block chunk to memory list
                raw_samples.extend(rgbBuffer)
                samples_collected += chunk_size
                print(f"Streaming data: {samples_collected}/{total_samples_to_record} samples captured...", end="\r")
                
    finally:
        # Disconnect hardware session cleanly
        dwf.FDwfDeviceClose(hdwf)
        print("\nHardware acquisition closed completed.")
    
    if save_raw and raw_samples:
        save_raw_signals_to_csv(raw_samples, sample_period_ns, filename=raw_filename)
        return True
    
    return False

def decode_differential_edges(input_file, output_file):
    """
    Calculates a differential signal, uses vectorised edge detection 
    to extract tri-level data (+1, -1), groups them by ignoring 5us gaps, 
    and converts to binary to decode 12-pulse trains.
    """
    # 1. Load the raw capture data
    try:
        df = pd.read_csv(input_file)
        time_data = df.iloc[:, 0].values
        
        # Calculate differential signal: Column 2 minus Column 3
        differential_signal = df.iloc[:, 1].values - df.iloc[:, 2].values
    except FileNotFoundError:
        print(f"Error: Could not locate '{input_file}'.")
        return
    except IndexError:
        print("Error: The CSV must contain at least three columns.")
        return

    # 2. Filter artefacts de glitching
    clean_signal = medfilt(differential_signal, kernel_size=5)

    # 3. Edge Detection Logic
    positive_active = (clean_signal > 0.8).astype(int)
    negative_active = (clean_signal < -0.8).astype(int)

    pos_transitions = np.where(np.diff(positive_active) == 1)[0] + 1
    neg_transitions = np.where(np.diff(negative_active) == 1)[0] + 1

    # 4. Compile and sort the detected pulses using vectorised arrays
    times_pos = time_data[pos_transitions]
    times_neg = time_data[neg_transitions]

    combined_times = np.concatenate((times_pos, times_neg))

    print(f"[DEBUG] Number of positive transitions detected : {len(pos_transitions)}")
    print(f"[DEBUG] Number of negative transitions detected : {len(neg_transitions)}")
    print(f"[DEBUG] Total of combined pulses : {len(combined_times)}")

    # Store as tri-level data: 1s for positive, -1s for negative
    combined_data = np.concatenate((np.ones(len(times_pos), dtype=int), 
                                    -np.ones(len(times_neg), dtype=int)))

    sort_order = np.argsort(combined_times)

    pulse_times = combined_times[sort_order]
    pulse_data = combined_data[sort_order]
    
    # 5. Group pulses into trains
    # Set threshold to 15us to ignore the 5us inter-pulse spacing 
    # and only split on the ~20us train gaps.
    gap_threshold = 5e3
    
    trains = []
    current_train = []
    last_time = None
    
    for t, level in zip(pulse_times, pulse_data):
        if not current_train:
            current_train.append(level)
            last_time = t
        else:
            if (t - last_time) > gap_threshold:
                trains.append(current_train[0:12])
                current_train = [level]
            else:
                current_train.append(level)
            last_time = t
            
    if current_train:
        trains.append(current_train[0:12])

    # 6. Convert to binary and decode into decimal values
    decimals = []
    for index, train in enumerate(trains):
        if len(train) == 12:
            # Map the tri-level -1 to binary 0 at the final step
            binary_train = [1 if val == 1 else 0 for val in train]
            
            # Join bits into a string and convert from base-2 to base-10
            bit_string = "".join(str(b) for b in binary_train)
            print(bit_string)
            decimals.append(int(bit_string,2))
        else:
            print(f"Artefact Warning: Train {index} contains {len(train)} pulses. Expected 12.")
            decimals.append(np.nan)


    for index, train in enumerate(trains):
        print(f"Train {index}: {len(train)} pulses")

    # 7. Output results
    output_df = pd.DataFrame({'Decoded_Decimal': decimals})
    output_df.to_csv(output_file, index=False)
    print(f"Decoding finished. Processed {len(decimals)} train(s). Results saved to '{output_file}'.")
    plt.plot(decimals)
    plt.title("Decoded Decimal Output")
    plt.xlabel("Sample Index")
    plt.ylabel("Value")
    plt.show()


# --- Execution Entry Point ---
if __name__ == "__main__":
    
    RAW_CSV_FILENAME = "raw_signals_capture.csv"
    DECODED_CSV_FILENAME = "decoded_serial_data.csv"
    
    # 1. Execute hardware capture
    print("--- Starting Data Capture ---")
    capture_success = capture_data(
        duration_sec=0.025,
        SR=50000000.0,
        save_raw=True,
        raw_filename=RAW_CSV_FILENAME
    )
    
    # 2. Proceed to decoding if capture was successful
    if capture_success:
        print("\n--- Starting Data Decoding ---")
        decode_differential_edges(RAW_CSV_FILENAME, DECODED_CSV_FILENAME)
    else:
        print("\nCapture failed or yielded no data. Skipping decoding step.")