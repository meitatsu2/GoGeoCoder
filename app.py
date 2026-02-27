import streamlit as st
import pandas as pd
import re
import time
import io

# --- 1. CORE LOGIC FUNCTIONS ---

def run_stage_1(name):
    """Stage 1: Recursive name stripping."""
    current_name = str(name)
    while len(current_name) > 1:
        # lat, lon = call_api(current_name) # API placeholder
        # if lat: return lat, lon, current_name
        current_name = current_name[:-1]
    return None, None, name

def run_stage_2(address):
    """Stage 2: Bracket POI/Intersection extraction."""
    brackets = re.findall(r'\((.*?)\)', str(address))
    for content in brackets:
        content = content.replace('近', '', 1).strip()
        if '/' in content or '與' in content:
            parts = re.split(r'/|與', content)
            rem1 = parts[0].strip()
            match = re.search(r'.*?([巷路街])', parts[1])
            rem2 = match.group(0) if match else parts[1]
            return {"Remark1": rem1, "Remark2": rem2, "Method": "Intersection"}
        else:
            rem = content.split('站')[0] + '站' if '站' in content else content
            return {"Remark1": rem, "Remark2": "", "Method": "Landmark"}
    return None

def run_stage_3(address):
    """Stage 3: Administrative Cleanup."""
    addr = str(address)
    addr = re.sub(r'\(.*?\)', '', addr)
    if '市' in addr and '區' not in addr:
        addr = re.sub(r'(?<=市).*?里', '', addr)
    else:
        addr = re.sub(r'(?<=[鎮區]).*?里', '', addr)
    addr = re.sub(r'\d+鄰', '', addr)
    for char in ['之', '-', '旁', '對面', '、', '，', '底']:
        addr = addr.split(char)[0]
    if '號' in addr:
        addr = addr.split('號')[0] + '號'
    return addr.strip()

# --- 2. SESSION STATE SETUP ---

if 'buffer' not in st.session_state:
    st.session_state.buffer = pd.DataFrame(columns=['Name1', 'Address1', 'Remark1', 'Remark2', 'Lat', 'Lon'])
if 'failure_log' not in st.session_state:
    st.session_state.failure_log = pd.DataFrame(columns=['Original_Name', 'Original_Address', 'Cleaned_Address1', 'Status'])
if 'scanned' not in st.session_state:
    st.session_state.scanned = 0

# --- 3. UI LAYOUT ---

st.set_page_config(page_title="GoGeoCoder", layout="wide")
st.title("📡 GoGeoCoder Command Center")

# Header Section
col_menu, col_metrics = st.columns([2, 1])

with col_menu:
    menu = st.selectbox("Menu", [
        "Select Action", 
        "Import XLSX Address List", 
        "Import Processed Coordinates in CSV", 
        "Export Processed Coordinates in CSV", 
        "Export Failure Log in CSV", 
        "Reset System"
    ])

with col_metrics:
    st.write(f"**Scanned/Total:** {st.session_state.scanned} | **Buffered:** {len(st.session_state.buffer)} | **Failed:** {len(st.session_state.failure_log)}")

# --- 4. MENU OPERATIONS ---

if menu == "Import XLSX Address List":
    uploaded = st.file_uploader("Select XLSX Source", type=["xlsx"])
    if uploaded:
        df_source = pd.read_excel(uploaded)
        st.write("File Loaded Successfully!") # Debug line
        st.write(df_source.columns.tolist())   # This will show you the column names it sees
        
        total_recs = len(df_source)
        
        # Progress UI
        pb_col, time_col, pause_col = st.columns([2, 1, 1])
        p_bar = pb_col.progress(0)
        time_display = time_col.empty()
        pause_switch = pause_col.checkbox("Pause / Resume")

        if st.button("Start Processing"):
            start_time = time.time()
            paused_duration = 0
            
            # Use index-based selection if names don't match exactly
            name_col = '站點名稱' if '站點名稱' in df_source.columns else df_source.columns[0]
            addr_col = '地址' if '地址' in df_source.columns else df_source.columns[1]

            for i, row in df_source.iterrows():
                if pause_switch:
                    p_start = time.time()
                    while pause_switch:
                        time.sleep(0.5)
                    paused_duration += (time.time() - p_start)
                
                name_src = row[name_col]
                addr_src = row[addr_col]
                
                # --- PROCESSING PIPELINE ---
                # For testing: setting a fake lat/lon to see if the counter moves
                lat, lon, name1 = 25.0, 121.0, name_src 
                
                # (Your existing Stage 1, 2, 3 logic goes here)

                # Update Counters & Buffer
                new_row = pd.DataFrame([{'Name1': name1, 'Lat': lat, 'Lon': lon}])
                st.session_state.buffer = pd.concat([st.session_state.buffer, new_row], ignore_index=True)
                st.session_state.scanned += 1
                
                # Progress updates...   

elif menu == "Import Processed Coordinates in CSV":
    up_csv = st.file_uploader("Upload CSV to Buffer", type="csv")
    if up_csv:
        st.session_state.buffer = pd.read_csv(up_csv)
        st.success("Buffer Updated.")

elif menu == "Export Processed Coordinates in CSV":
    if not st.session_state.buffer.empty:
        csv = st.session_state.buffer.to_csv(index=False).encode('utf-8-sig')
        st.download_button("Download Success Buffer", csv, "buffer.csv", "text/csv")

elif menu == "Export Failure Log in CSV":
    if not st.session_state.failure_log.empty:
        csv = st.session_state.failure_log.to_csv(index=False).encode('utf-8-sig')
        st.download_button("Download Failure Log", csv, "failures.csv", "text/csv")

elif menu == "Reset System":
    if st.button("Clear All Data"):
        st.session_state.clear()
        st.rerun()