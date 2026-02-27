import streamlit as st
import pandas as pd
import re
import time
import requests

# --- 1. GEOCODING ENGINE ---
def get_real_coordinates(query):
    # This pulls the key from the 'Secrets' you set in Streamlit Cloud
    api_key = st.secrets.get("GOOGLE_MAPS_API_KEY")
    if not api_key or not query or len(query) < 5:
        return None, None
    
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": query, "key": api_key, "language": "zh-TW"}
    try:
        resp = requests.get(url, params=params, timeout=5).json()
        if resp.get('status') == 'OK':
            loc = resp['results'][0]['geometry']['location']
            return loc['lat'], loc['lng']
    except:
        pass
    return None, None

def run_stage_1(name):
    current_name = str(name)
    while len(current_name) > 2: # Stop at 2 chars to avoid generic junk searches
        lat, lon = get_real_coordinates(f"Gogoro {current_name}")
        if lat: return lat, lon, current_name
        current_name = current_name[:-1]
    return None, None, name

def run_stage_2(address):
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
    addr = str(address)
    addr = re.sub(r'\(.*?\)', '', addr) # Strip brackets
    
    # Improved Stage 3: Remove '里' only if it's following a District/City
    addr = re.sub(r'(?<=[區鎮市])[^路街巷]*?里', '', addr)
    addr = re.sub(r'\d+鄰', '', addr)
    
    # Strip administrative noise but KEEP the road name
    for char in ['之', '-', '旁', '對面', '、', '，', '底']:
        addr = addr.split(char)[0]
    if '號' in addr:
        addr = addr.split('號')[0] + '號'
        
    cleaned = addr.strip()
    lat, lon = get_real_coordinates(cleaned)
    return cleaned, lat, lon

# --- 2. SESSION STATE ---
columns = ['Name1', 'Address1', 'Remark1', 'Remark2', 'Lat', 'Lon']
if 'buffer' not in st.session_state:
    st.session_state.buffer = pd.DataFrame(columns=columns)
if 'failure_log' not in st.session_state:
    st.session_state.failure_log = pd.DataFrame(columns=columns)
if 'scanned' not in st.session_state:
    st.session_state.scanned = 0

# --- 3. UI ---
st.set_page_config(page_title="GoGeoCoder", layout="wide")
st.title("📡 GoGeoCoder Command Center")

col_menu, col_metrics = st.columns([2, 1])
with col_menu:
    menu = st.selectbox("Menu", ["Select Action", "Import XLSX Address List", "Import Processed Coordinates in CSV", "Export Processed Coordinates in CSV", "Export Failure Log in CSV", "Reset System"])

with col_metrics:
    st.write(f"**Scanned/Total:** {st.session_state.scanned} | **Buffered:** {len(st.session_state.buffer)} | **Failed:** {len(st.session_state.failure_log)}")

# --- 4. OPERATIONS ---
if menu == "Import XLSX Address List":
    uploaded = st.file_uploader("Select XLSX Source", type=["xlsx"])
    if uploaded:
        df_source = pd.read_excel(uploaded)
        total_recs = len(df_source)
        
        pb_col, time_col, pause_col = st.columns([2, 1, 1])
        p_bar = pb_col.progress(0)
        time_display = time_col.empty()
        pause_switch = pause_col.checkbox("Pause / Resume")

        if st.button("Start Processing"):
            start_time = time.time()
            paused_duration = 0
            for i, row in df_source.iterrows():
                if pause_switch:
                    p_start = time.time()
                    while pause_switch: time.sleep(0.5)
                    paused_duration += (time.time() - p_start)
                
                name_src, addr_src = row.get('站點名稱', ''), row.get('地址', '')
                lat, lon, name1, address1, remark1, remark2 = None, None, name_src, "", "", ""

                # Try Stage 1
                lat, lon, name1 = run_stage_1(name_src)
                
                # Try Stage 2
                if not lat:
                    s2 = run_stage_2(addr_src)
                    if s2:
                        remark1, remark2, lat, lon = s2['Remark1'], s2['Remark2'], s2['Lat'], s2['Lon']
                
                # Try Stage 3
                if not lat:
                    address1, lat, lon = run_stage_3(addr_src)

                record = {'Name1': name1, 'Address1': address1, 'Remark1': remark1, 'Remark2': remark2, 'Lat': lat if lat else "Fail", 'Lon': lon if lon else "Fail"}

                if lat and lon:
                    st.session_state.buffer = pd.concat([st.session_state.buffer, pd.DataFrame([record])], ignore_index=True)
                else:
                    st.session_state.failure_log = pd.concat([st.session_state.failure_log, pd.DataFrame([record])], ignore_index=True)
                
                st.session_state.scanned += 1
                active_time = (time.time() - start_time) - paused_duration
                avg = active_time / (i + 1)
                rem = avg * (total_recs - (i + 1))
                p_bar.progress((i + 1) / total_recs)
                time_display.text(f"ETA: {int(rem // 60)}m {int(rem % 60)}s")
            st.success("Task Complete!")
# (Remaining menu logic for Export and Reset remains the same)
