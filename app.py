import streamlit as st
import pandas as pd
import re
import time
import requests

# --- 1. PERSISTENT STATE ---
if 'idx' not in st.session_state: st.session_state.idx = 0
if 'run' not in st.session_state: st.session_state.run = False
if 'buffer' not in st.session_state:
    st.session_state.buffer = pd.DataFrame(columns=['Name1', 'Address1', 'Remark1', 'Remark2', 'Lat', 'Lon'])
if 'fails' not in st.session_state:
    st.session_state.fails = pd.DataFrame(columns=['Name1', 'Address1', 'Remark1', 'Remark2', 'Lat', 'Lon'])

# --- 2. API ENGINE ---
def call_google(query):
    key = st.secrets.get("GOOGLE_MAPS_API_KEY")
    if not key or not query or len(str(query)) < 2: return None, None
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    try:
        r = requests.get(url, params={"address": query, "key": key, "language": "zh-TW"}).json()
        if r.get("status") == "OK":
            loc = r["results"][0]["geometry"]["location"]
            return loc["lat"], loc["lng"]
    except: pass
    return None, None

# --- 3. TREATMENT LOGIC (STEP 1) ---
def treat_record(row):
    # 1.1 Name1 (Remove last char)
    name_src = str(row.get('站點名稱', ''))
    name1 = name_src[:-1] if name_src else ""

    # 1.2 Remark Extraction (Brackets)
    addr_src = str(row.get('地址', ''))
    rem1, rem2 = "", ""
    brackets = re.findall(r'\((.*?)\)', addr_src)
    for content in brackets:
        content = content.replace('近', '', 1).strip()
        if '/' in content or '與' in content:
            parts = re.split(r'/|與', content)
            rem1 = parts[0].strip()
            # Loop from right of divider to find Lane, then Road
            r_side = parts[1].strip()
            match = re.search(r'.*?巷', r_side)
            if not match: match = re.search(r'.*?[路街]', r_side)
            rem2 = match.group(0) if match else r_side
        else:
            rem1 = content.split('站')[0] + '站' if '站' in content else content
    
    # 1.3 Address Cleanup (Address1)
    a1 = re.sub(r'\(.*?\)', '', addr_src)
    a1 = re.sub(r'(?<=[區鎮])[^區鎮]*?里', '', a1)
    if '市' in a1 and '區' not in a1: a1 = re.sub(r'(?<=市).*?里', '', a1)
    a1 = re.sub(r'\d+鄰', '', a1)
    for char in ['之', '-', '旁', '對面', '、', '，', '底']: a1 = a1.split(char)[0]
    if '號' in a1: a1 = a1.split('號')[0] + '號'
    
    return name1, a1.strip(), rem1, rem2

# --- 4. MOBILE UI ---
st.set_page_config(layout="wide")

# Title Row
t1, t2 = st.columns([1, 4])
t1.markdown("### GoGeoCoder")
t2.markdown("<p style='padding-top:10px; color:gray;'>v1.2 (Stable)</p>", unsafe_allow_html=True)

# Compact Menu & Counters Row
m_col, c_col = st.columns([1.5, 1])
with m_col:
    menu = st.selectbox("Menu", [
        "Import XLSX Address List", "Export Processed CSV", "Export Failure Log CSV", "Reset System"
    ], label_visibility="collapsed")

with c_col:
    total = st.session_state.get('total', 0)
    st.markdown(f"""
    <div style='font-size:0.8em; text-align:right;'>
    <b>S/T:</b> {st.session_state.idx}/{total}<br>
    <b>B:</b> {len(st.session_state.buffer)} | <b>F:</b> {len(st.session_state.fails)}
    </div>
    """, unsafe_allow_html=True)

# --- 5. OPERATIONS ---
if menu == "Import XLSX Address List":
    file = st.file_uploader("Select XLSX Source", type=["xlsx"])
    if file:
        df = pd.read_excel(file)
        st.session_state.total = len(df)
        
        # Progress & Pause Button Row
        pb_col, btn_col = st.columns([3, 1])
        p_bar = pb_col.progress(st.session_state.idx / st.session_state.total if st.session_state.total > 0 else 0)
        
        # Step 2: Search Loop
        if st.session_state.run:
            if btn_col.button("⏸ Pause", type="primary", use_container_width=True):
                st.session_state.run = False
                st.rerun()
            
            # Use a while loop to prevent freezing at the end
            while st.session_state.idx < st.session_state.total and st.session_state.run:
                idx = st.session_state.idx
                row = df.iloc[idx]
                n1, a1, r1, r2 = treat_record(row)
                lat, lon = None, None

                # Geocoding Waterfall
                if '號' in a1: lat, lon = call_google(a1) # 2.1
                if not lat and r1 and r2: lat, lon = call_google(f"{r1} {r2}") # 2.2
                if not lat and r1: lat, lon = call_google(r1) # 2.3
                if not lat: lat, lon = call_google(n1) # 2.4

                rec = {'Name1': n1, 'Address1': a1, 'Remark1': r1, 'Remark2': r2, 'Lat': lat, 'Lon': lon}
                if lat:
                    st.session_state.buffer = pd.concat([st.session_state.buffer, pd.DataFrame([rec])], ignore_index=True)
                else:
                    st.session_state.fails = pd.concat([st.session_state.fails, pd.DataFrame([rec])], ignore_index=True)
                
                st.session_state.idx += 1
                if st.session_state.idx % 5 == 0 or st.session_state.idx == st.session_state.total:
                    st.rerun()
        else:
            if btn_col.button("▶️ Resume" if st.session_state.idx > 0 else "▶️ Start", type="secondary", use_container_width=True):
                st.session_state.run = True
                st.rerun()

elif menu == "Export Processed CSV":
    if not st.session_state.buffer.empty:
        st.download_button("Download Success", st.session_state.buffer.to_csv(index=False).encode('utf-8-sig'), "success.csv", use_container_width=True)

elif menu == "Export Failure Log CSV":
    if not st.session_state.fails.empty:
        st.download_button("Download Fails", st.session_state.fails.to_csv(index=False).encode('utf-8-sig'), "fails.csv", use_container_width=True)

elif menu == "Reset System":
    if st.button("Confirm Hard Reset", type="primary"):
        st.session_state.clear()
        st.rerun()