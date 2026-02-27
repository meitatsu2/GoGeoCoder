import streamlit as st
import pandas as pd
import re
import time

# --- STAGE-BASED PROCESSING LOGIC ---

def process_stage_1(name):
    # Logic: Search name, if fail, strip right-most character and retry
    # Note: Replace with actual API call (Google/TGOS)
    temp_name = str(name)
    while len(temp_name) > 1:
        # result = call_api(temp_name)
        # if result: return result, temp_name
        temp_name = temp_name[:-1]
    return None, name

def process_stage_2(address):
    # Logic: Focus on brackets (...)
    brackets = re.findall(r'\((.*?)\)', str(address))
    for content in brackets:
        content = content.replace('近', '', 1)
        # Case 1: Intersections
        if '/' in content or '與' in content:
            parts = re.split(r'/|與', content)
            remark1 = parts[0].strip()
            # Find 1st 巷, 路, or 街
            match = re.search(r'.*?[巷路街]', parts[1])
            remark2 = match.group(0) if match else parts[1]
            # lat, lon = call_intersection_api(remark1, remark2)
            return {"Remark1": remark1, "Remark2": remark2, "Lat": None, "Lon": None}
        # Case 2: Landmarks
        else:
            remark1 = content.split('站')[0] + '站' if '站' in content else content
            # lat, lon = call_landmark_api(remark1)
            return {"Remark1": remark1, "Remark2": "", "Lat": None, "Lon": None}
    return None

def process_stage_3(address):
    # Logic: Aggressive Cleanup
    addr = re.sub(r'\(.*?\)', '', str(address)) # Remove brackets
    addr = re.sub(r'[^區鎮市]*?[里]', '', addr) # Remove 里 and preceding
    addr = re.sub(r'\d+鄰', '', addr) # Remove 鄰 and preceding num
    # Remove after specific characters
    for char in ['之', '-', '旁', '對面', '、', '，', '底']:
        addr = addr.split(char)[0]
    # Keep only up to '號'
    if '號' in addr:
        addr = addr.split('號')[0] + '號'
    return addr

# --- STREAMLIT UI ---

st.set_page_config(layout="wide")

# Header with Dropdown and Counters
col1, col2 = st.columns([2, 1])

with col1:
    menu = st.selectbox("Menu", 
                        ["Select Action", "Import XLSX Address List", 
                         "Import Processed Coordinates in CSV", 
                         "Export Processed Coordinates in CSV", "Reset System"])

# Counters at Right
if 'scanned' not in st.session_state:
    st.session_state.update({'scanned': 0, 'total': 0, 'buffered': 0, 'failed': 0, 'pause': False})

with col2:
    st.write(f"**Scanned / Total:** {st.session_state.scanned} / {st.session_state.total} | **Buffered:** {st.session_state.buffered} | **Failed:** {st.session_state.failed}")

# Action: Import XLSX
if menu == "Import XLSX Address List":
    uploaded_file = st.file_uploader("Select Source XLSX", type=["xlsx", "csv"])
    
    if uploaded_file:
        df_source = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        st.session_state.total = len(df_source)
        
        # Buffer Data Structure
        buffer = []
        
        # Controls: Progress Bar & Pause/Resume
        pb_col, ctrl_col = st.columns([3, 1])
        progress_bar = pb_col.progress(0)
        time_text = pb_col.empty()
        
        pause_button = ctrl_col.checkbox("Pause Execution")

        if st.button("Execute Geocoding"):
            for i, row in df_source.iterrows():
                # Check for Pause
                while pause_button:
                    time.sleep(1)
                
                name_src = row['站點名稱']
                addr_src = row['地址']
                
                # Execution Pipeline
                res_1, name1 = process_stage_1(name_src)
                
                if not res_1:
                    res_2 = process_stage_2(addr_src)
                    if not res_2:
                        address1 = process_stage_3(addr_src)
                        # Stage 3 geocoding call here
                    else:
                        # Map Stage 2 results
                        pass
                
                # Update Counters
                st.session_state.scanned += 1
                # (Update buffered/failed based on API success)
                
                # Update Progress
                percent = (i + 1) / st.session_state.total
                progress_bar.progress(percent)
                time_text.text(f"Completion: {percent*100:.1f}% | Est. Remaining: Calculating...")