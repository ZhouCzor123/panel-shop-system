import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO
import re

PASSWORD = "PanelShopSecure2026"

# Hardcoded service account credentials dictionary to completely bypass picky TOML parsers
service_account_info = {
    "project_id": "aqueous-glyph-502919-b1",
    "private_key_id": "3fe21201df09ef4fa447b63a02c26ce8c96aa76d",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDJSVUyHuN9UriE\nIqekP9i64Qb+r8FvjNBa9AtgRcqrQMuvRuikKsBwRqPnLbsShOPuuLCvqtzY02uS\nnBeGkmObTgZmHQw3IiRyEk3If4keAAidVJ0/KEYp89KPpH3S4J0adNycczynw8\nJ1\nvNxOEmJDbh3Zqqc2G1Owqg38od/DwTtwSEjWmq/ACdSYdJTiY4Mw8BxaqTRLH0SWO\nnn3kgw9RpP4CgzkYv/YRM/pipSit+6LAzgrwHdeIccLuziEzDhfBlgWtjGrVnywFQ\nnc/P4+biLGMxgkxwyrIJXrQgpca3DMZdM1R8fvKowt5pwNVb8PgKIZYCKQD2\nkcqD\nc3HF3KhHAgMBAAECggEAJjF6dHTYQn/h4DcpL98byIKYcrwxHbDz1jHrC6YyXgBY\nPqLOnYmRslIT6yq87wVQKK0jLQnXtUS=mDPOnsmNMY6t+LZL4SI51z2StM5H9ZwS\nn+ABHf/bu+IzNhh/8SSoCKTIAaQjZWM50kUDCwwzb5x2YrBMUeBMbPcI8yh\nTU4Nx8\nxXYMNhsfaIHUKmb6lOCk+NxOQWQInpDcGdfq0h/pRpEd5SsFkXPbP+cum6yQrWYnt\nwKd1M488o8cK02g4tHC6VT7EQnd9o5XT47q/GexR/gCpcv2cd1/PcA/ZwJoHh2ww\nhKjwI0s4o/Fa8aPdZdnTfftk2PjIigyYjdkjvSVVOKBgQD5Ny2kkbz\nBzmE9o4w\ntPzeXYPgiq2esAUtjQQ93hBcWCt1yZmL+MKtaxzyU+LNYNlDuqvXg3PaTweQuz9g\nnTkTv7ZPWntrZlPKmB9fm7DdbksOc0mTGfAER1j/0X25Y+9++I83owHS1LfprRiD\nqM3abBwl8NduXIPZHhQg0Ak2dKBgQDoB1jm+QxeqSgnPbrnG00JD9\n/t=6gcBSLE\nnaEo4EgWNDi7f/YXN3IaEPXVZgLL/6JZCRR/4d2aGLj0Yc7W4gpa19LyEjvBtiN7z\nn5KS34akwvTc2Q3zzNZPLYKzAlPFecNzu17lTfwxo4SbAB/YYeOGLWT/Pdt+onsIb\nT7Dcai3sKwBGbDFRNCY4maFd6c5gPeTS88lwFfFPDBxquTEyXUy\nNMOYIsKUIjkr\nNC+fnj/iOERYWOY2GNKVbwif7N6jy2YHIRFNYFu/jzXJZATCJmrzRwzf3DXLKWLx\nn08IVGhKVoEWG+pCJx1j9M2/Mj8jMw1c1p+05ia0dTmF6Xif0t5YMGFNAoGaB8L2\ nta2V1dxs6DnSa3UdEsJmcLhzTiA1r3Hq5K13ZiYmMLXv/hR1Oz\njuxHMZ9dRdLSmx\nYlp6RiDYCnMMQ4VnxMDoIzgj0JIuy@qhjvBkC+yC7Lzi++ViY63e0TEP4ezcn+5o\nn5iQvUsS6rvjgeOYyjlg+ZLqt4eN5oUGmtd5CVDsCgYBW9Mp3PMBoESMS2ewoClPa\nnqhMBNHF0N0UXhoy4z92wdKahNyNCnqU2YbOZKH33AKPVEOx\nnvuKEnlGXr37mTaV\neCy3Xub19FjNd/+4/cK5G1twrGdlq91S3kMelHjIKYc1wlbegsXvLAHC6/NGCgn\nn9N9JdFHdzhQq2jubD8TYPg==\n-----END PRIVATE KEY-----\n",
    "client_email": "panel-shop-editor@aqueous-glyph-502919-b1.iam.gserviceaccount.com",
    "client_id": "101211345603545895002",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/panel-shop-editor%40aqueous-glyph-502919-b1.iam.gserviceaccount.com"
}

# Connect to Google Sheets by passing only the service account credentials
conn = st.connection(
    "gsheets",
    type=GSheetsConnection,
    **service_account_info
)

def load_permanent_data():
    df = conn.read(spreadsheet=st.secrets.get("spreadsheet", ""), worksheet="Inventory", ttl=0)
    df['Part Number'] = df['Part Number'].astype(str)
    if 'Min Qty' not in df.columns:
        df['Min Qty'] = 0
    return df

def save_permanent_data(df):
    conn.update(spreadsheet=st.secrets.get("spreadsheet", ""), worksheet="Inventory", data=df)
    st.cache_data.clear()

def load_logs():
    df = conn.read(spreadsheet=st.secrets.get("spreadsheet", ""), worksheet="Logs", ttl=0)
    df['Part Number'] = df['Part Number'].astype(str)
    return df

def save_logs(df):
    conn.update(spreadsheet=st.secrets.get("spreadsheet", ""), worksheet="Logs", data=df)
    st.cache_data.clear()

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
    pattern = r"^[A-G][1-3]$"
    return bool(re.match(pattern, clean_loc)), clean_loc

def generate_barcode_image(part_number):
    try:
        buffer = BytesIO()
        Code128(str(part_number), writer=ImageWriter()).write(buffer)
        return buffer.getvalue()
    except Exception:
        return None

def highlight_shortages(row):
    try:
        min_qty = float(row['Min Qty']) if pd.notna(row['Min Qty']) else 0
        current_qty = float(row['Qty on Hand']) if pd.notna(row['Qty on Hand']) else 0
    except ValueError:
        min_qty, current_qty = 0, 0
    
    if current_qty <= min_qty and min_qty > 0:
        return ['background-color: #ffcccc; color: #900000; font-weight: bold'] * len(row)
    return [''] * len(row)

st.set_page_config(
    page_title="Panel Shop Inventory", 
    page_icon="BlackMcDonald_Logo.webp", 
    layout="wide"
)

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
                    col1, col2, col3, col4, col5, col6 = st.columns(6)
                    col1.metric("Part Number", str(row['Part Number']))
                    col2.metric("Part Name", str(row['Part Name']))
                    col3.metric("Quantity", int(row['Qty on Hand']))
                    col4.metric("Location", f"[{row['Location']}]")
                    col5.metric("Project Name", str(row['Project']))
                    col6.metric("Min Qty Alert Level", int(row['Min Qty']) if pd.notna(row['Min Qty']) else 0)
                    
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
            new_loc = st.text_input("Storage Location (Allowed: A1-A3 up to G1-G3):")
            new_proj = st.text_input("Project Name:")
            new_min_qty = st.number_input("Minimum Quantity Alert Threshold (Optional, set 0 for None):", min_value=0, step=1, value=0)
            
            if st.button("Save Brand New Item"):
                valid, formatted_loc = is_valid_location(new_loc)
                if not valid:
                    st.error("Invalid Location! Format must be Rack A-G and Shelf 1-3. Example: F2")
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
                            "Location": formatted_loc, "Project": new_proj, "Min Qty": new_min_qty
                        }])
                        df = pd.concat([df, new_row], ignore_index=True)
                        save_permanent_data(df)
                        log_event("Added", new_num, new_name, f"Registered new item. Initial Qty: {new_qty} at {formatted_loc}. Min Qty Limit set to {new_min_qty}")
                        st.success("Successfully registered item permanently!")
                        st.rerun()
        else:
            options = [f"{row['Part Name']} | Project: {row['Project']} | Current Qty: {row['Qty on Hand']} | Location: {row['Location']}" for idx, row in results.iterrows()]
            choice = st.selectbox("Select the correct item row to add stock to:", options, key="add_select")
            row_idx = results.index[options.index(choice)]
            
            amt_to_add = st.number_input("How many units are you adding?", min_value=1, step=1, key="add_amt")
            new_min_qty = st.number_input(f"Update Minimum Quantity Alert Level (Current: {df.at[row_idx, 'Min Qty']}):", min_value=0, step=1, value=int(df.at[row_idx, 'Min Qty']))
            
            if st.button("Confirm Addition"):
                df.at[row_idx, 'Qty on Hand'] += amt_to_add
                df.at[row_idx, 'Min Qty'] = new_min_qty
                save_permanent_data(df)
                log_event("Added", df.at[row_idx, 'Part Number'], df.at[row_idx, 'Part Name'], f"Added {amt_to_add} units. New Total: {df.at[row_idx, 'Qty on Hand']}. Min Qty adjusted to {new_min_qty}")
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
                min_threshold = df.at[row_idx, 'Min Qty']
                new_stock = current_stock - amt_to_sub
                
                if new_stock <= 0:
                    df = df.drop(row_idx).reset_index(drop=True)
                    log_event("Removed", part_num, part_name, f"Removed {amt_to_sub} units. Stock hit 0, item deleted.")
                    st.toast(f"🚨 ALERT: {part_name} has hit 0 and is completely out of stock!", icon="🚨")
                    st.success("Item quantity dropped to 0 and has been removed from permanent inventory!")
                else:
                    df.at[row_idx, 'Qty on Hand'] = new_stock
                    log_event("Removed", part_num, part_name, f"Removed {amt_to_sub} units. Remaining: {new_stock}")
                    
                    if new_stock <= min_threshold and min_threshold > 0:
                        st.warning(f"⚠️ LOW STOCK ALERT: {part_name} is down to {new_stock} units! (Minimum threshold: {min_threshold})")
                        st.toast(f"Low Stock Alert: {part_name} needs reordering!", icon="⚠️")
                    else:
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
            
            new_location = st.text_input(f"Enter new location code (Allowed: A1-A3 up to G1-G3):")
            if st.button("Update Location"):
                valid, formatted_loc = is_valid_location(new_location)
                if not valid:
                    st.error("Invalid Location! Must be a letter from A-G and a number from 1-3. Example: F1")
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
styled_df = df.style.apply(highlight_shortages, axis=1)
st.sidebar.dataframe(styled_df, use_container_width=True)

# --- Your Permanent Legacy Footer ---
st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div style='text-align: center; color: gray; font-size: 0.8em;'>
        <b>Panel Shop Inventory System v2.0</b><br>
        Designed & Built by <b>Zhou lung Czornoba</b><br>
        Co-op Term May-August 2026
    </div>
    """, 
    unsafe_allow_html=True
)
