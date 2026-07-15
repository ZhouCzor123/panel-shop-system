import streamlit as st
import pandas as pd
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO
import re
import os

DATA_FILE = "inventory_data.json"
LOG_FILE = "inventory_log.json"
PASSWORD = "PanelShopSecure2026"

def load_permanent_data():
    if os.path.exists(DATA_FILE):
        return pd.read_json(DATA_FILE, dtype={'Part Number': str})
    else:
        return pd.DataFrame(columns=['Part Number', 'Part Name', 'Qty on Hand', 'Location', 'Project'])

def save_permanent_data(df):
    df.to_json(DATA_FILE, orient="records")

def load_logs():
    if os.path.exists(LOG_FILE):
        return pd.read_json(LOG_FILE, dtype={'Part Number': str})
    else:
        return pd.DataFrame(columns=['Timestamp', 'Action', 'Part Number', 'Part Name', 'Details'])

def save_logs(df):
    df.to_json(LOG_FILE, orient="records")

def log_event(action, part_num, part_name, details):
    log_df = load_logs()
    new_log = pd.DataFrame([{
        'Timestamp': pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        'Action': action,
        'Part Number': str(part_num),
        'Part Name': str(part_name),
        'Details': str(details)
    }])
    log_df = pd.concat([log_df, new_log], ignore_index=True)
    save_logs(log_df)

def is_valid_location(loc_string):
    clean_loc = loc_string.strip().upper()
    pattern = r"^[A-E][1-3]$"
    return bool(re.match(pattern, clean_loc)), clean_loc

def generate_barcode_image(part_number):
    try:
        buffer = BytesIO()
        Code128(str(part_number), writer=ImageWriter()).write(buffer)
        return buffer.getvalue()
    except Exception:
        return None

st.set_page_config(page_title="Panel Shop Inventory", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("Panel Shop Inventory Login")
    user_pass = st.text_input("Enter Shop Password:", type="password")
    if st.button("Login"):
        if user_pass == PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect Password. Access Denied.")
    st.stop()

st.title("Panel Shop Barcode Inventory System")
df = load_permanent_data()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Scan Search", 
    "Add Inventory", 
    "Take Inventory", 
    "Change Part Location",
    "Log History"
])

with tab1:
    st.header("Search Database")
    search_query = st.text_input("Click here to SCAN a barcode, or TYPE a part name/number:", key="search_input").strip()
    
    if search_query:
        results = df[
            (df['Part Number'].astype(str) == search_query) | 
            (df['Part Name'].str.contains(search_query, case=False, na=False))
        ]
        
        if not results.empty:
            st.success(f"Found {len(results)} matching item(s):")
            for idx, row in results.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns(5)
                    col1.metric("Part Number", str(row['Part Number']))
                    col2.metric("Part Name", str(row['Part Name']))
                    col3.metric("Quantity", int(row['Qty on Hand']))
                    col4.metric("Location", f"[{row['Location']}]")
                    col5.metric("Project Name", str(row['Project']))
                    
                    barcode_img = generate_barcode_image(str(row['Part Number']))
                    if barcode_img:
                        st.image(barcode_img, caption=f"Visual Label Representation for {row['Part Number']}", width=300)
                        
                        st.download_button(
                            label=f"Download Printable Label for {row['Part Number']}",
                            data=barcode_img,
                            file_name=f"label_{row['Part Number']}.png",
                            mime="image/png",
                            key=f"dl_{idx}"
                        )
                    st.markdown("---")
        else:
            st.error(f"No parts match your search for '{search_query}'.")

with tab2:
    st.header("Receive / Add Stock")
    add_query = st.text_input("Scan or Type part to ADD stock:", key="add_input").strip()
    
    if add_query:
        results = df[
            (df['Part Number'].astype(str) == add_query) | 
            (df['Part Name'].str.contains(add_query, case=False, na=False))
        ]
        
        if results.empty:
            st.info("Brand new item detected! Fill out the fields below to register it:")
            new_num = st.text_input("Part Number (This will become the barcode text):")
            new_name = st.text_input("Part Name:")
            new_qty = st.number_input("Initial Quantity:", min_value=1, step=1)
            new_loc = st.text_input("Storage Location (Allowed: A1-A3 up to E1-E3):")
            new_proj = st.text_input("Project Name:")
            
            if st.button("Save Brand New Item"):
                valid, formatted_loc = is_valid_location(new_loc)
                if not valid:
                    st.error("Invalid Location! Format must be Rack A-E and Shelf 1-3. Example: B2")
                else:
                    duplicate_check = df[
                        (df['Part Number'] == new_num) & 
                        (df['Location'] == formatted_loc) & 
                        (df['Project'] == new_proj)
                    ]
                    
                    if not duplicate_check.empty:
                        st.error("This exact part is already registered at this location for this project.")
                    else:
                        new_row = pd.DataFrame([{
                            "Part Number": new_num, "Part Name": new_name, "Qty on Hand": new_qty, 
                            "Location": formatted_loc, "Project": new_proj
                        }])
                        df = pd.concat([df, new_row], ignore_index=True)
                        save_permanent_data(df)
                        log_event("Added", new_num, new_name, f"Registered new item. Initial Qty: {new_qty} at {formatted_loc}")
                        st.success("Successfully registered item permanently!")
                        st.rerun()
        else:
            options = [f"{row['Part Name']} | Project: {row['Project']} | Current Qty: {row['Qty on Hand']} | Location: {row['Location']}" for idx, row in results.iterrows()]
            choice = st.selectbox("Select the correct item row to add stock to:", options, key="add_select")
            row_idx = results.index[options.index(choice)]
            
            amt_to_add = st.number_input("How many units are you adding?", min_value=1, step=1, key="add_amt")
            if st.button("Confirm Addition"):
                df.at[row_idx, 'Qty on Hand'] += amt_to_add
                save_permanent_data(df)
                log_event("Added", df.at[row_idx, 'Part Number'], df.at[row_idx, 'Part Name'], f"Added {amt_to_add} units. New Total: {df.at[row_idx, 'Qty on Hand']}")
                st.success("Stock updated permanently!")
                st.rerun()

with tab3:
    st.header("Remove / Assemble Stock")
    take_query = st.text_input("Scan or Type part to TAKE stock:", key="take_input").strip()
    
    if take_query:
        results = df[
            (df['Part Number'].astype(str) == take_query) | 
            (df['Part Name'].str.contains(take_query, case=False, na=False))
        ]
        
        if results.empty:
            st.error("Part not found. Please verify the name or number.")
        else:
            options = [f"{row['Part Name']} | Project: {row['Project']} | Current Qty: {row['Qty on Hand']} | Location: {row['Location']}" for idx, row in results.iterrows()]
            choice = st.selectbox("Select the item row you are pulling from:", options, key="take_select")
            row_idx = results.index[options.index(choice)]
            
            amt_to_sub = st.number_input("How many units are you taking for assembly?", min_value=1, step=1, key="take_amt")
            if st.button("Confirm Removal"):
                current_stock = df.at[row_idx, 'Qty on Hand']
                part_num = df.at[row_idx, 'Part Number']
                part_name = df.at[row_idx, 'Part Name']
                new_stock = current_stock - amt_to_sub
                
                if new_stock <= 0:
                    df = df.drop(row_idx).reset_index(drop=True)
                    log_event("Removed", part_num, part_name, f"Removed {amt_to_sub} units. Stock hit 0, item deleted.")
                    st.success("Item quantity dropped to 0 and has been removed from live inventory!")
                else:
                    df.at[row_idx, 'Qty on Hand'] = new_stock
                    log_event("Removed", part_num, part_name, f"Removed {amt_to_sub} units. Remaining: {new_stock}")
                    st.success(f"Stock removed! Remaining units: {new_stock}")
                
                save_permanent_data(df)
                st.rerun()

with tab4:
    st.header("Move Parts to a New Location/Bin")
    loc_query = st.text_input("Scan or Type part to change its LOCATION:", key="loc_input").strip()
    
    if loc_query:
        results = df[
            (df['Part Number'].astype(str) == loc_query) | 
            (df['Part Name'].str.contains(loc_query, case=False, na=False))
        ]
        
        if results.empty:
            st.error("Part not found.")
        else:
            options = [f"{row['Part Name']} | Project: {row['Project']} | Current Location: {row['Location']}" for idx, row in results.iterrows()]
            choice = st.selectbox("Select the item listing you want to move:", options, key="loc_select")
            row_idx = results.index[options.index(choice)]
            
            new_location = st.text_input(f"Enter new location code (Allowed: A1-A3 up to E1-E3):")
            if st.button("Update Location"):
                valid, formatted_loc = is_valid_location(new_location)
                if not valid:
                    st.error("Invalid Location! Must be a letter from A-E and a number from 1-3. Example: C1")
                else:
                    old_loc = df.at[row_idx, 'Location']
                    part_num = df.at[row_idx, 'Part Number']
                    part_name = df.at[row_idx, 'Part Name']
                    
                    df.at[row_idx, 'Location'] = formatted_loc
                    save_permanent_data(df)
                    log_event("Moved", part_num, part_name, f"Moved from {old_loc} to {formatted_loc}")
                    st.success(f"Location permanently updated to [{formatted_loc}]!")
                    st.rerun()

with tab5:
    st.header("Activity Log History")
    log_df = load_logs()
    if log_df.empty:
        st.info("No activity logged yet.")
    else:
        action_filter = st.selectbox("Filter by Action:", ["All", "Added", "Removed", "Moved"])
        filtered_logs = log_df
        if action_filter != "All":
            filtered_logs = log_df[log_df['Action'] == action_filter]
        
        st.dataframe(filtered_logs.iloc[::-1], use_container_width=True)

st.sidebar.header("Live Inventory Grid View")
st.sidebar.dataframe(df, use_container_width=True)
