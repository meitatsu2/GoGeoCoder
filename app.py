import streamlit as st
import pandas as pd
import re
import time
import io
import requests

# --- 1. GEOCODING ENGINE & API INTEGRATION ---

def get_real_coordinates(query):
    """
    Stage-Gate API Caller. 
    Replace the return None with actual API request logic when ready.
    """
    # Example for Google Maps (Uncomment and add key to st.secrets):
    # api_key = st.secrets.get("GOOGLE_MAPS_API_KEY")
    # if api_key and query:
    #     url = f"https://maps.googleapis.com/maps/api/geocode/json?address={query}&key={api_key}"
    #     response = requests.get(url).json()
    #     if response.get('status') == 'OK':
    #         loc = response['results'][0]['geometry']['location']
    #         return loc['lat'], loc['lng']
    
    return None, None

def run_stage_1(name):
    """Stage 1: Recursive name stripping."""
    current_name = str(name)
    while len(current_name) > 1:
        lat, lon = get_real_coordinates(f"Gogoro {current_name}")
        if lat: return lat, lon, current_name
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
            lat, lon = get_real_coordinates(f"{rem1} {rem2}")
            return {"Remark1": rem1, "Remark2": rem2, "Lat": lat, "Lon": lon}
        else:
            rem = content.split('站')[0] + '站' if '站' in content else content
            lat, lon = get_real_coordinates(rem)
            return {"Remark1": rem, "Remark2": "", "Lat": lat, "Lon": lon}
    return None

def run_stage_3(address):
    """Stage 3: Administrative Cleanup Logic."""
    addr = str(address)
    addr = re.sub(r'\(.*?\)', '', addr) # Remove brackets
    
    # '里' cleanup based on context
    if '市' in addr and '區' not in addr:
        addr = re.sub(r'(?<=市).*?里', '', addr)
    else:
        addr = re.sub(r'(?<=[鎮區]).*?里', '', addr)
        
    addr = re.sub(r'\d+鄰', '', addr) # Remove '鄰'
    
    # Remove after specific characters
    for char in ['之', '-', '旁', '對面', '、', '，', '底']:
        addr = addr.split(char)[0]
        
    if '號' in addr:
        addr = addr.split('號')[0] + '號'
        
    cleaned_addr = addr.strip()
    lat, lon = get_real_coordinates(cleaned_addr)
    return cleaned_addr, lat, lon

# --- 2. SESSION STATE SETUP ---

if 'buffer' not in st.session_state:
    st.session_state.buffer = pd.DataFrame(columns=['Name1', 'Address1', 'Remark1', 'Remark2', 'Lat', 'Lon'])
if 'failure_log' not in st.session_state:
    st.session_state.failure_log = pd.DataFrame(columns=['Original_Name', 'Original_Address', 'Cleaned_Address1', 'Status'])
if 'scanned' not in st.session_state:
    st.session_state.scanned = 0

# --- 3. UI SETUP ---

st.set_page_config(page_title="GoGeoCoder", layout="wide")
st.title("📡 GoGeoCoder Command Center")

# Menu and Counters Row
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
        total_recs = len(df_source)
        st.info(f"File Loaded. Columns: {df_source.columns.tolist()}")
        
        # Progress UI Row
        pb_col, time_col, pause_col = st.columns([2, 1, 1])
        p_bar = pb_col.progress(0)
        time_display = time_col.empty()
        pause_switch = pause_col.checkbox("Pause / Resume")

        if st.button("Start Processing"):
            start_time = time.time()
            paused_duration = 0
            
            for i, row in df_source.iterrows():
                # --- PAUSE LOGIC ---
                if pause_switch:
                    p_start = time.time()
                    while pause_switch:
                        time.sleep(0.5)
                    paused_duration += (time.time() - p_start)
                
                name_src = row.get('站點名稱', '')
                addr_src = row.get('地址', '')
                
                lat, lon = None, None
                name1, address1, remark1, remark2 = name_src, "", "", ""

                # --- 3-STAGE PIPELINE ---
                
                # Stage 1: Name recursive strip
                lat, lon, name1 = run_stage_1(name_src)
                
                # Stage 2: Bracket POI
                if not lat:
                    s2 = run_stage_2(addr_src)
                    if s2:
                        remark1, remark2 = s2['Remark1'], s2['Remark2']
                        lat, lon = s2['Lat'], s2['Lon']
                
                # Stage 3: Admin Cleanup
                if not lat:
                    address1, lat, lon = run_stage_3(addr_src)

                # --- UPDATE RESULTS ---
                if lat and lon:
                    new_row = pd.DataFrame([{'Name1': name1, 'Address1': address1, 'Remark1': remark1, 'Remark2': remark2, 'Lat': lat, 'Lon': lon}])
                    st.session_state.buffer = pd.concat([st.session_state.buffer, new_row], ignore_index=True)
                else:
                    fail_row = pd.DataFrame([{'Original_Name': name_src, 'Original_Address': addr_src, 'Cleaned_Address1': address1, 'Status': 'No GPS'}])
                    st.session_state.failure_log = pd.concat([st.session_state.failure_log, fail_row], ignore_index=True)
                
                # --- TIMER & UI UPDATES ---
                st.session_state.scanned += 1
                active_time = (time.time() - start_time) - paused_duration
                avg_time = active_time / (i + 1)
                rem_sec = avg_time * (total_recs - (i + 1))
                
                p_bar.progress((i + 1) / total_recs)
                time_display.text(f"ETA: {int(rem_sec // 60)}m {int(rem_sec % 60)}s")
            
            st.success("Batch Processing Complete!")

elif menu == "Import Processed Coordinates in CSV":
    up_csv = st.file_uploader("Upload CSV to Buffer", type="csv")
    if up_csv:
        st.session_state.buffer = pd.read_csv(up_csv)
        st.success(f"Buffer Restored: {len(st.session_state.buffer)} records.")

elif menu == "Export Processed Coordinates in CSV":
    if not st.session_state.buffer.empty:
        csv_data = st.session_state.buffer.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Download Success Buffer (CSV)", csv_data, "GoStation_Success.csv", "text/csv")
        st.dataframe(st.session_state.buffer)

elif menu == "Export Failure Log in CSV":
    if not st.session_state.failure_log.empty:
        csv_fail = st.session_state.failure_log.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Download Failure Log (CSV)", csv_fail, "GoStation_Failures.csv", "text/csv")
        st.dataframe(st.session_state.failure_log)

elif menu == "Reset System":
    st.warning("This will clear all memory and reset counters.")
    if st.button("Confirm Reset"):
        st.session_state.clear()
        st.rerun()