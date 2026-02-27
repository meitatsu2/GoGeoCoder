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
    st.session_state.fails = pd.DataFrame(columns=['Name1', 'Address1', 'Remark1', 'Remark2', 'Lat', 'Lon', 'Reason'])

# --- 2. THE ENGINE (With Error Capture) ---
def call_google(query):
    key = st.secrets.get("GOOGLE_MAPS_API_KEY")
    if not key: return None, None, "Secret Key Missing"
    
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    try:
        r = requests.get(url, params={"address": query, "key": key, "language": "zh-TW"}, timeout=10).json()
        status = r.get("status")
        if status == "OK":
            loc = r["results"][0]["geometry"]["location"]
            return loc["lat"], loc["lng"], "OK"
        return None, None, status # Returns: REQUEST_DENIED, OVER_QUERY_LIMIT, etc.
    except Exception as e:
        return None, None, str(e)

# --- 3. TREATMENT LOGIC (STEP 1) ---
def treat_record(row):
    name_src = str(row.get('站點名稱', ''))
    n1 = name_src[:-1] if name_src else ""
    addr_src = str(row.get('地址', ''))
    r1, r2 = "", ""
    brackets = re.findall(r'\((.*?)\)', addr_src)
    for content in brackets:
        content = content.replace('近', '', 1).strip()
        if '/' in content or '與' in content:
            parts = re.split(r'/|與', content)
            r1 = parts[0].strip()
            r_side = parts[1].strip()
            match = re.search(r'.*?巷', r_side)
            if not match: match = re.search(r'.*?[路街]', r_side)
            r2 = match.group(0) if match else r_side
        else:
            r1 = content.split('站')[0] + '站' if '站' in content else content
    
    a1 = re.sub(r'\(.*?\)', '', addr_src)
    a1 = re.sub(r'(?<=[區鎮])[^區鎮]*?里', '', a1)
    if '市' in a1 and '區' not in a1: a1 = re.sub(r'(?<=市).*?里', '', a1)
    a1 = re.sub(r'\d+鄰', '', a1)
    for char in ['之', '-', '旁', '對面', '、', '，', '底']: a1 = a1.split(char)[0]
    if '號' in a1: a1 = a1.split('號')[0] + '號'
    
    return n1, a1.strip(), r1, r2

# --- 4. MOBILE UI ---
st.set_page_config(layout="wide", page_title="GoGeoCoder")

# Title and Version
t_col, v_col = st.columns([2, 1])
t_col.markdown("### GoGeoCoder <span style='font-size:14px; color:gray;'>v1.4</span>", unsafe_allow_html=True)

# Compact Menu & Counters
m_col, c_col = st.columns([1.8, 1.2])
with m_col:
    menu = st.selectbox("Menu", 
                        ["Import xlsx address list", "Export Processed CSV", "Export Failure Log CSV", "Reset System"], 
                        label_visibility="collapsed")

with c_col:
    total = st.session_state.get('total', 0)
    st.markdown(f"""
    <div style='font-size:0.85em; text-align:right; border-left:2px solid #ddd; padding-left:10px;'>
    <b>S/T:</b> {st.session_state.idx}/{total}<br>
    <b>B:</b> {len(st.session_state.buffer)} | <b>F:</b> {len(st.session_state.fails)}
    </div>
    """, unsafe_allow_html=True)

# --- 5. OPERATIONS ---
if menu == "Import xlsx address list":
    file = st.file_uploader("Upload", type=["xlsx"], label_visibility="collapsed")
    if file:
        df = pd.read_excel(file)
        st.session_state.total = len(df)
        
        pb_col, btn_col = st.columns([3, 1])
        p_bar = pb_col.progress(st.session_state.idx / st.session_state.total if st.session_state.total > 0 else 0)
        
        if st.session_state.run:
            if btn_col.button("⏸ Pause", type="primary", use_container_width=True):
                st.session_state.run = False
                st.rerun()
            
            while st.session_state.idx < st.session_state.total and st.session_state.run:
                idx = st.session_state.idx
                n1, a1, r1, r2 = treat_record(df.iloc[idx])
                lat, lon, status = None, None, "Fail"

                # Step 2: Waterfall Geocoding
                if '號' in a1: lat, lon, status = call_google(a1)
                if not lat and r1 and r2: lat, lon, status = call_google(f"{r1} {r2}")
                if not lat and r1: lat, lon, status = call_google(r1)
                if not lat: lat, lon, status = call_google(n1)

                rec = {'Name1': n1, 'Address1': a1, 'Remark1': r1, 'Remark2': r2, 'Lat': lat, 'Lon': lon}
                if lat:
                    st.session_state.buffer = pd.concat([st.session_state.buffer, pd.DataFrame([rec])], ignore_index=True)
                else:
                    rec['Reason'] = status
                    st.session_state.fails = pd.concat([st.session_state.fails, pd.DataFrame([rec])], ignore_index=True)
                
                st.session_state.idx += 1
                if st.session_state.idx % 5 == 0 or st.session_state.idx == st.session_state.total:
                    st.rerun()
        else:
            btn_text = "▶️ Resume" if st.session_state.idx > 0 else "▶️ Start"
            if btn_col.button(btn_text, type="secondary", use_container_width=True):
                st.session_state.run = True
                st.rerun()

elif menu == "Export Processed CSV":
    if not st.session_state.buffer.empty:
        st.download_button("Download Success", st.session_state.buffer.to_csv(index=False).encode('utf-8-sig'), "success.csv", use_container_width=True)

elif menu == "Export Failure Log CSV":
    if not st.session_state.fails.empty:
        st.download_button("Download Fail Log", st.session_state.fails.to_csv(index=False).encode('utf-8-sig'), "fails.csv", use_container_width=True)
        st.write("### Diagnostics")
        st.dataframe(st.session_state.fails)

elif menu == "Reset System":
    if st.button("Confirm Reset", type="primary"):
        st.session_state.clear()
        st.rerun()