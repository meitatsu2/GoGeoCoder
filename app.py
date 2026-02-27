import streamlit as st
import pandas as pd
import re

# --- STAGE 1 & 2 LOGIC ---
def clean_for_api(name, address):
    # Strip parentheses and floor info for Stage 1 accuracy
    addr = re.sub(r'\(.*?\)', '', str(address))
    addr = re.sub(r'\d+樓.*', '', addr).replace('對面', '').strip()
    # Optimized search string for Stage 3
    poi_query = f"Gogoro {name} {addr}"
    return addr, poi_query

# --- MOBILE UI SETUP ---
st.set_page_config(page_title="GoStation Radar", layout="centered")

st.title("📡 Radar Geocoder")
st.write("Upload your failure list to start the 3-Stage process.")

uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.success(f"Loaded {len(df)} records")

    if st.button("🚀 Start Stage 1: Normalization"):
        df['Cleaned_Addr'], df['POI_Query'] = zip(*df.apply(
            lambda x: clean_for_api(x['Name'], x['Address']), axis=1
        ))
        
        st.dataframe(df[['Name', 'Cleaned_Addr']].head())
        
        # Download button for mobile
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Cleaned List",
            data=csv,
            file_name='cleaned_gostations.csv',
            mime='text/csv',
        )