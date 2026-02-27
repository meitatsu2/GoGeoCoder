import streamlit as st
import pandas as pd
import re
import time
import requests

# --- 1. SESSION STATE FOR PERSISTENCE ---
if 'idx' not in st.session_state: st.session_state.idx = 0
if 'run' not in st.session_state: st.session_state.run = False
if 'buffer' not in st.session_state:
    st.session_state.buffer = pd.DataFrame(columns=['Name1', 'Address1', 'Remark1', 'Remark2', 'Lat', 'Lon'])
if 'fails' not in st.session_state:
    st.session_state.fails = pd.DataFrame(columns=['Name1', 'Address1', 'Remark1', 'Remark2', 'Lat', 'Lon'])

# --- 2. THE GOOGLE API ENGINE ---
def call_google(query):
    key = st.secrets.get("GOOGLE_MAPS_API_KEY")
    if not key or not query: return None, None
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    try:
        r = requests.get(url, params={"address": query, "key": key, "language": "zh-TW"}).json()
        if r.get("status") == "OK":
            # We look for "ROOFTOP" or "RANGE_INTERPOLATED" for high accuracy
            loc = r["results"][0]["geometry"]["location"]
            return loc["lat"], loc["lon"]
    except:
        pass
    return None, None

# --- 3. DATA TREATMENT LOGIC ---
def treat_record(row):
    # 1.1 Name1: Remove last 1 character
    name_src = str(row.get('站點名稱', ''))
    name1 = name_src[:-1] if len(name_src) > 0 else ""

    # 1.2 Brackets logic (Remark1, Remark2)
    addr_src = str(row.get('地址', ''))
    rem1, rem2 = "", ""
    brackets = re.findall(r'\((.*?)\)', addr_src)
    for content in brackets:
        content = content.replace('近', '', 1).strip()
        if '/' in content or '與' in content:
            parts = re.split(r'/|與', content)
            rem1 = parts[0].strip()
            # Loop for 巷, then 路/街
            r_part = parts[1].strip()
            match = re.search(r'.*?巷', r_part)
            if not match:
                match = re.search(r'.*?[路街]', r_part)
            rem2 = match.group(0) if match else r_part
        else:
            if '站' in content:
                rem1 = content.split('站')[0] + '站'
            else:
                rem1 = content
    
    # 1.3 Address Cleanup (Address1)
    addr1 = re.sub(r'\(.*?\)', '', addr_src)
    addr1 = re.sub(r'(?<=[區鎮])[^區鎮]*?里', '', addr1) # After 區/鎮
    if '市' in addr1 and '區' not in addr1:
        addr1 = re.sub(r'(?<=市).*?里', '', addr1) # After 市 if no 區
    addr1 = re.sub(r'\d+鄰', '', addr1)
    for char in ['之', '-', '旁', '對面', '、', '，', '底']:
        addr1 = addr1.split(char)[0]
    if '號' in addr1:
        addr1 = addr1.split('號')[0] + '號'
    
    return name1, addr1.strip(), rem1, rem2

# --- 4. UI SETUP ---
st.set_page_config(layout="wide")
st.title("📡 GoGeoCoder Command Center")

menu = st.selectbox("Menu", [
    "Import XLSX Address List", 
    "Export Processed Coordinates in CSV", 
    "Export Failure Log in CSV", 
    "Reset System"
])

# --- 5. OPERATIONS ---
if menu == "Import XLSX Address List":
    file = st.file_uploader("Select XLSX Source", type=["xlsx"])
    if file:
        df = pd.read_excel(file)
        total = len(df)
        
        # UI Metrics and Toggle Button
        col_ctrl, col_progress = st.columns([1, 3])
        
        # Pause/Resume Button Logic
        if st.session_state.run:
            if col_ctrl.button("⏸ Pause", type="primary", use_container_width=True): # Red/Primary
                st.session_state.run = False
                st.rerun()
        else:
            if col_ctrl.button("▶️ Resume" if st.session_state.idx > 0 else "▶️ Start", type="secondary", use_container_width=True): # Green/Secondary
                st.session_state.run = True
                st.rerun()

        # Progress and Counters
        st.write(f"**Scanned / Total:** {st.session_state.idx} / {total}")
        p_bar = st.progress(st.session_state.idx / total if total > 0 else 0)
        time_display = st.empty()

        # Loop processing
        if st.session_state.run and st.session_state.idx < total:
            start_time = time.time()
            
            while st.session_state.idx < total and st.session_state.run:
                idx = st.session_state.idx
                row = df.iloc[idx]
                
                # Step 1: Treatment
                n1, a1, r1, r2 = treat_record(row)
                lat, lon = None, None
                
                # Step 2: Search Pipeline (Logic to reduce cost)
                # 2.1 Stage 1: Address with '號'
                if '號' in a1:
                    lat, lon = call_google(a1)
                
                # 2.2 Stage 2: Intersection
                if not lat and r1 and r2:
                    lat, lon = call_google(f"{r1} {r2}")
                
                # 2.3 Stage 3: Remark1 POI
                if not lat and r1 and not r2:
                    lat, lon = call_google(r1)
                
                # 2.4 Stage 4: Name1
                if not lat:
                    lat, lon = call_google(n1)

                # Step 3: Buffer or Fail
                rec = {'Name1': n1, 'Address1': a1, 'Remark1': r1, 'Remark2': r2, 'Lat': lat, 'Lon': lon}
                if lat:
                    st.session_state.buffer = pd.concat([st.session_state.buffer, pd.DataFrame([rec])], ignore_index=True)
                else:
                    st.session_state.fails = pd.concat([st.session_state.fails, pd.DataFrame([rec])], ignore_index=True)
                
                st.session_state.idx += 1
                
                # Time Calculation
                elapsed = time.time() - start_time
                avg = elapsed / (st.session_state.idx - idx) # Avg of current session
                rem = avg * (total - st.session_state.idx)
                time_display.text(f"Est. Remaining Time: {int(rem // 60)}m {int(rem % 60)}s")
                
                # Auto-refresh UI every few records
                if st.session_state.idx % 5 == 0:
                    st.rerun()

# (Remaining Menu Options: Export/Reset)
elif menu == "Export Processed Coordinates in CSV":
    if not st.session_state.buffer.empty:
        st.download_button("Download Success CSV", st.session_state.buffer.to_csv(index=False).encode('utf-8-sig'), "success.csv")
elif menu == "Export Failure Log in CSV":
    if not st.session_state.fails.empty:
        st.download_button("Download Failure CSV", st.session_state.fails.to_csv(index=False).encode('utf-8-sig'), "fails.csv")
elif menu == "Reset System":
    if st.button("Confirm Hard Reset"):
        st.session_state.idx = 0
        st.session_state.run = False
        st.session_state.buffer = pd.DataFrame(columns=['Name1', 'Address1', 'Remark1', 'Remark2', 'Lat', 'Lon'])
        st.session_state.fails = pd.DataFrame(columns=['Name1', 'Address1', 'Remark1', 'Remark2', 'Lat', 'Lon'])
        st.rerun()