import streamlit as st
import pandas as pd
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO
import re

PASSWORD = "PanelShopSecure2026"

if "inventory_db" not in st.session_state:
    st.session_state["inventory_db"] = pd.DataFrame(
        columns=['Part Number', 'Part Name', 'Qty on Hand', 'Location', 'Project']
    )

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
df = st.session_state["inventory_db"]

tab1, tab2, tab3, tab4 = st.tabs([
    "Scan Search", 
    "Add Inventory", 
    "Take Inventory", 
    "Change Part Location"
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
                        st.session_state["inventory_db"] = pd.concat([df, new_row], ignore_index=True)
                        st.success("Successfully registered item in system memory!")
                        st.rerun()
        else:
            options = [f"{row['Part Name']} | Project: {row['Project']} | Current Qty: {row['Qty on Hand']} | Location: {row['Location']}" for idx, row in results.iterrows()]
            choice = st.selectbox("Select the correct item row to add stock to:", options, key="add_select")
            row_idx = results.index[options.index(choice)]
            
            amt_to_add = st.number_input("How many units are you adding?", min_value=1, step=1, key="add_amt")
            if st.button("Confirm Addition"):
                st.session_state["inventory_db"].at[row_idx, 'Qty on Hand'] += amt_to_add
                st.success("Stock updated successfully!")
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
                new_stock = current_stock - amt_to_sub
                
                if new_stock <= 0:
                    st.session_state["inventory_db"] = df.drop(row_idx).reset_index(drop=True)
                    st.success("Item quantity dropped to 0 and has been removed from live inventory!")
                else:
                    st.session_state["inventory_db"].at[row_idx, 'Qty on Hand'] = new_stock
                    st.success(f"Stock removed! Remaining units: {new_stock}")
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
                    st.session_state["inventory_db"].at[row_idx, 'Location'] = formatted_loc
                    st.success(f"Location updated to [{formatted_loc}]!")
                    st.rerun()

st.sidebar.header("Live Inventory Grid View")
st.sidebar.dataframe(st.session_state["inventory_db"], use_container_width=True)
