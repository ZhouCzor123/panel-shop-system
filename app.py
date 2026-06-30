import streamlit as st
import pandas as pd
import os
import re

# --- CONFIGURATION ---
EXCEL_FILE = "PanelShop.Inventory+.xlsx"
PASSWORD = "PanelShopSecure2026"  

def load_data():
    if os.path.exists(EXCEL_FILE):
        return pd.read_excel(EXCEL_FILE, dtype={'Part Number': str, 'Barcode': str})
    else:
        df = pd.DataFrame(columns=['Part Number', 'Part Name', 'Qty on Hand', 'Location', 'Project', 'Barcode'])
        df.to_excel(EXCEL_FILE, index=False)
        return df

def save_data(df):
    df.to_excel(EXCEL_FILE, index=False)

def is_valid_location(loc_string):
    """Validates that location matches Rack A-E and Shelf 1-3 (e.g., A1, B3, E2)"""
    # Clean up spaces and convert to uppercase
    clean_loc = loc_string.strip().upper()
    # Regular expression: Starts with A, B, C, D, or E, followed exactly by 1, 2, or 3
    pattern = r"^[A-E][1-3]$"
    return bool(re.match(pattern, clean_loc)), clean_loc

# --- WEB PAGE SETUP ---
st.set_page_config(page_title="Panel Shop Inventory", page_icon="⚡", layout="wide")

# --- PASSWORD GATE ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 Panel Shop Inventory Login")
    user_pass = st.text_input("Enter Shop Password:", type="password")
    if st.button("Login"):
        if user_pass == PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("❌ Incorrect Password. Access Denied.")
    st.stop()

# --- APP HEADER & DATA LOADING ---
st.title("⚡ Panel Shop Barcode Inventory System")
df = load_data()

tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Scan & Search", 
    "📥 Add Inventory (+)", 
    "📤 Take Inventory (-)", 
    "📍 Change Part Location"
])

def smart_search(query):
    if not query:
        return pd.DataFrame()
    return df[
        (df['Barcode'] == query) | 
        (df['Part Number'] == query) | 
        (df['Part Name'].str.contains(query, case=False, na=False))
    ]

# --- TAB 1: SCAN & SEARCH ---
with tab1:
    st.header("Search Database")
    search_query = st.text_input("Click here to SCAN a barcode, or TYPE a part name/number:", key="search_input").strip()
    
    if search_query:
        results = smart_search(search_query)
        if not results.empty:
            st.success(f"Found {len(results)} matching item(s):")
            for idx, row in results.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5, col6 = st.columns(6)
                    col1.metric("Part Number", str(row['Part Number']))
                    col2.metric("Part Name", str(row['Part Name']))
                    col3.metric("Quantity", int(row['Qty on Hand']))
                    col4.metric("Location", f"[{row['Location']}]")
                    col5.metric("Project Name", str(row['Project']))
                    col6.metric("Barcode Value", str(row['Barcode']))
                    st.markdown("---")
        else:
            st.error(f"No parts match your search for '{search_query}'.")

# --- TAB 2: ADD INVENTORY (+) ---
with tab2:
    st.header("Receive / Add Stock")
    add_query = st.text_input("Scan or Type part to ADD stock:", key="add_input").strip()
    
    if add_query:
        results = smart_search(add_query)
        if results.empty:
            st.info("💡 Brand new item detected! Fill out the cells below to add it to Excel:")
            new_num = st.text_input("Part Number:")
            new_name = st.text_input("Part Name:")
            new_qty = st.number_input("Initial Quantity:", min_value=0, step=1)
            
            # Location input with validation rules
            new_loc = st.text_input("Storage Location (Allowed: A1-A3 up to E1-E3):")
            
            new_proj = st.text_input("Project Name:")
            new_bar = st.text_input("Barcode String (Leave blank to match Part Number):")
            
            if st.button("Save Brand New Item"):
                valid, formatted_loc = is_valid_location(new_loc)
                if not valid:
                    st.error("❌ Invalid Location! Format must be a Rack letter (A-E) followed by a Shelf number (1-3). Example: B2")
                else:
                    final_barcode = new_bar if new_bar else new_num
                    new_row = pd.DataFrame([{
                        "Part Number": new_num, "Part Name": new_name, "Qty on Hand": new_qty, 
                        "Location": formatted_loc, "Project": new_proj, "Barcode": final_barcode
                    }])
                    df = pd.concat([df, new_row], ignore_index=True)
                    save_data(df)
                    st.success(f"Successfully written to Excel at location [{formatted_loc}]!")
                    st.rerun()
        else:
            options = [f"{row['Part Name']} | Project: {row['Project']} | Current Qty: {row['Qty on Hand']} | Location: {row['Location']}" for idx, row in results.iterrows()]
            choice = st.selectbox("Select the correct item row to add stock to:", options, key="add_select")
            row_idx = results.index[options.index(choice)]
            
            amt_to_add = st.number_input("How many units are you adding?", min_value=1, step=1, key="add_amt")
            if st.button("Confirm Addition"):
                df.at[row_idx, 'Qty on Hand'] += amt_to_add
                save_data(df)
                st.success(f"Excel updated! New Total: {df.at[row_idx, 'Qty on Hand']}")
                st.rerun()

# --- TAB 3: TAKE INVENTORY (-) ---
with tab3:
    st.header("Remove / Assemble Stock")
    take_query = st.text_input("Scan or Type part to TAKE stock:", key="take_input").strip()
    
    if take_query:
        results = smart_search(take_query)
        if results.empty:
            st.error("Part not found. Please verify the name, number, or barcode.")
        else:
            options = [f"{row['Part Name']} | Project: {row['Project']} | Current Qty: {row['Qty on Hand']} | Location: {row['Location']}" for idx, row in results.iterrows()]
            choice = st.selectbox("Select the item row you are pulling from:", options, key="take_select")
            row_idx = results.index[options.index(choice)]
            
            amt_to_sub = st.number_input("How many units are you taking for assembly?", min_value=1, step=1, key="take_amt")
            if st.button("Confirm Removal"):
                current_stock = df.at[row_idx, 'Qty on Hand']
                df.at[row_idx, 'Qty on Hand'] = max(0, current_stock - amt_to_sub)
                save_data(df)
                st.success(f"Excel updated! Remaining Stock: {df.at[row_idx, 'Qty on Hand']}")
                st.rerun()

# --- TAB 4: CHANGE PART LOCATION ---
with tab4:
    st.header("Move Parts to a New Location/Bin")
    loc_query = st.text_input("Scan or Type part to change its LOCATION:", key="loc_input").strip()
    
    if loc_query:
        results = smart_search(loc_query)
        if results.empty:
            st.error("Part not found.")
        else:
            options = [f"{row['Part Name']} | Project: {row['Project']} | Current Location: {row['Location']}" for idx, row in results.iterrows()]
            choice = st.selectbox("Select the item listing you want to move:", options, key="loc_select")
            row_idx = results.index[options.index(choice)]
            
            new_location = st.text_input(f"Enter new location code (Allowed: A1-A3 up to E1-E3 | Current: {df.at[row_idx, 'Location']}):")
            if st.button("Update Location Cell"):
                valid, formatted_loc = is_valid_location(new_location)
                if not valid:
                    st.error("❌ Invalid Location! Must be a letter from A-E and a number from 1-3. Example: C1")
                else:
                    df.at[row_idx, 'Location'] = formatted_loc
                    save_data(df)
                    st.success(f"Location cell updated to [{formatted_loc}] in the Excel database!")
                    st.rerun()

st.sidebar.header("📋 Live Excel Grid View")
st.sidebar.dataframe(df, use_container_width=True)
