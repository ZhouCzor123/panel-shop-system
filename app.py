import streamlit as st
import pandas as pd
from supabase import create_client, Client
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO
import re
import pytz

PASSWORD = "PanelShopSecure2026"

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def load_permanent_data():
    try:
        response = supabase.table("Inventory").select("*").execute()
        df = pd.DataFrame(response.data)
        if df.empty:
            df = pd.DataFrame(columns=['Part Number', 'Part Name', 'Part Type', 'Qty on Hand', 'Location', 'Project Under', 'Min Qty'])
        else:
            if 'id' in df.columns:
                df = df.drop(columns=['id'])
            if 'Project' in df.columns and 'Project Under' not in df.columns:
                df.rename(columns={'Project': 'Project Under'}, inplace=True)
            df = df[df['Part Number'] != "___DUMMY___"]
            df['Part Number'] = df['Part Number'].astype(str)
            if 'Part Type' not in df.columns:
                df['Part Type'] = ""
            if 'Min Qty' not in df.columns:
                df['Min Qty'] = 0
        return df
    except Exception:
        return pd.DataFrame(columns=['Part Number', 'Part Name', 'Part Type', 'Qty on Hand', 'Location', 'Project Under', 'Min Qty'])

def save_permanent_data(df):
    try:
        clean_df = df.copy()
        clean_df['Qty on Hand'] = clean_df['Qty on Hand'].fillna(0).astype(int)
        clean_df['Min Qty'] = clean_df['Min Qty'].fillna(0).astype(int)
        clean_df = clean_df.fillna("")
        
        if 'id' in clean_df.columns:
            clean_df = clean_df.drop(columns=['id'])
            
        data_to_insert = clean_df.to_dict(orient="records")
        
        if data_to_insert:
            supabase.table("Inventory").upsert(data_to_insert).execute()
            supabase.table("Inventory").delete().eq("Part Number", "___DUMMY___").execute()

        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error saving to database: {e}")

def load_logs():
    try:
        response = supabase.table("Logs").select("*").execute()
        df = pd.DataFrame(response.data)
        if df.empty:
            df = pd.DataFrame(columns=['Timestamp', 'Action', 'Part Number', 'Part Name', 'Project Under', 'Part Type', 'Details'])
        else:
            if 'id' in df.columns:
                df = df.drop(columns=['id'])
            if 'Project' in df.columns and 'Project Under' not in df.columns:
                df.rename(columns={'Project': 'Project Under'}, inplace=True)
            df = df[df['Action'] != "___DUMMY___"]
            df['Part Number'] = df['Part Number'].astype(str)
            for col in ['Project Under', 'Part Type']:
                if col not in df.columns:
                    df[col] = ""
        return df
    except Exception:
        return pd.DataFrame(columns=['Timestamp', 'Action', 'Part Number', 'Part Name', 'Project Under', 'Part Type', 'Details'])

def save_logs(df):
    try:
        clean_df = df.copy().fillna("")
        if 'id' in clean_df.columns:
            clean_df = clean_df.drop(columns=['id'])
            
        data_to_insert = clean_df.to_dict(orient="records")
        if data_to_insert:
            supabase.table("Logs").upsert(data_to_insert).execute()
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error saving logs: {e}")

def log_event(action, part_num, part_name, details, project_under="", part_type=""):
    eastern_tz = pytz.timezone('America/Toronto')
    current_time = pd.Timestamp.now(tz=eastern_tz).strftime("%Y-%m-%d %H:%M:%S")
    
    new_log = pd.DataFrame([{
        'Timestamp': current_time,
        'Action': action,
        'Part Number': str(part_num),
        'Part Name': str(part_name),
        'Project Under': str(project_under),
        'Part Type': str(part_type),
        'Details': str(details)
    }])
    save_logs(new_log)

def is_valid_location(loc_string):
    clean_loc = loc_string.strip().upper()
    pattern = r"^([C-E][1-4]|[A-B][1-3]|[F-G][1-3])$"
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

# --- DIALOG POPUPS ---
@st.dialog("Confirm Part Addition")
def confirm_add_dialog(action_type, details_dict):
    st.write("Are you sure you want to proceed with this inventory addition?")
    if action_type == "NEW_ITEM":
        st.markdown(f"**Part Number:** `{details_dict['Part Number']}`")
        st.markdown(f"**Part Name:** {details_dict['Part Name']}")
        st.markdown(f"**Type:** {details_dict['Part Type']} | **Qty:** {details_dict['Qty on Hand']}")
        st.markdown(f"**Location:** [{details_dict['Location']}] | **Project:** {details_dict['Project Under']}")
    else:
        st.markdown(f"**Adding:** {details_dict['amt_to_add']} unit(s) to **{details_dict['part_name']}**")
        st.markdown(f"**New Total:** {details_dict['new_total']}")

    col_yes, col_no = st.columns(2)
    if col_yes.button("Yes", key="pop_add_yes"):
        st.session_state["pending_action_confirmed"] = True
        st.rerun()
    if col_no.button("No", key="pop_add_no"):
        st.session_state["pending_action"] = None
        st.rerun()

@st.dialog("Confirm Part Removal")
def confirm_take_dialog(details_dict):
    st.write("Are you sure you want to remove stock for assembly?")
    st.markdown(f"**Taking:** {details_dict['amt_to_sub']} unit(s) from **{details_dict['part_name']}**")
    st.markdown(f"**Remaining Stock Will Be:** {details_dict['new_stock']}")

    col_yes, col_no = st.columns(2)
    if col_yes.button("Yes", key="pop_take_yes"):
        st.session_state["pending_action_confirmed"] = True
        st.rerun()
    if col_no.button("No", key="pop_take_no"):
        st.session_state["pending_action"] = None
        st.rerun()

@st.dialog("Confirm Part Alteration")
def confirm_alter_dialog(details_dict):
    st.write("Are you sure you want to update these part attributes?")
    if details_dict['old_part_num'] != details_dict['updated_part_num']:
        st.markdown(f"**Part Number Change:** `{details_dict['old_part_num']}` ➔ `{details_dict['updated_part_num']}`")
    else:
        st.markdown(f"**Part Number:** `{details_dict['updated_part_num']}`")
    st.markdown(f"**New Name:** {details_dict['updated_name']}")
    st.markdown(f"**New Project:** {details_dict['updated_project']}")
    st.markdown(f"**New Type:** {details_dict['updated_type']}")

    col_yes, col_no = st.columns(2)
    if col_yes.button("Yes", key="pop_alter_yes"):
        st.session_state["pending_action_confirmed"] = True
        st.rerun()
    if col_no.button("No", key="pop_alter_no"):
        st.session_state["pending_action"] = None
        st.rerun()


st.set_page_config(
    page_title="Panel Shop Inventory System", 
    page_icon="BlackMcDonald_Logo.webp", 
    layout="wide"
)

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if "pending_action" not in st.session_state:
    st.session_state["pending_action"] = None
if "pending_action_confirmed" not in st.session_state:
    st.session_state["pending_action_confirmed"] = False

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

st.title("Panel Shop Inventory System")
df = load_permanent_data()

# --- CONFIRMATION DISPATCHER ---
if st.session_state["pending_action"] and not st.session_state["pending_action_confirmed"]:
    act = st.session_state["pending_action"]
    if act["type"] in ["ADD_NEW", "ADD_EXISTING"]:
        confirm_add_dialog(act["type"], act["data"])
    elif act["type"] == "TAKE":
        confirm_take_dialog(act["data"])
    elif act["type"] == "ALTER":
        confirm_alter_dialog(act["data"])

# Execute action if confirmed
if st.session_state["pending_action_confirmed"]:
    act = st.session_state["pending_action"]
    
    if act["type"] == "ADD_NEW":
        data = act["data"]
        new_row = pd.DataFrame([data])
        df = pd.concat([df, new_row], ignore_index=True)
        save_permanent_data(df)
        log_event("Added", data["Part Number"], data["Part Name"], f"Registered new item. Initial Qty: {data['Qty on Hand']} at {data['Location']}.", project_under=data["Project Under"], part_type=data["Part Type"])
        st.success("Successfully registered item permanently!")

    elif act["type"] == "ADD_EXISTING":
        data = act["data"]
        idx = data["row_idx"]
        df.at[idx, 'Qty on Hand'] += data["amt_to_add"]
        df.at[idx, 'Min Qty'] = data["new_min_qty"]
        save_permanent_data(df)
        log_event("Added", df.at[idx, 'Part Number'], df.at[idx, 'Part Name'], f"Added {data['amt_to_add']} units. New Total: {df.at[idx, 'Qty on Hand']}.", project_under=df.at[idx, 'Project Under'], part_type=df.at[idx, 'Part Type'])
        st.success("Stock updated permanently!")

    elif act["type"] == "TAKE":
        data = act["data"]
        idx = data["row_idx"]
        amt_to_sub = data["amt_to_sub"]
        new_stock = data["new_stock"]
        part_num = data["part_num"]
        part_name = data["part_name"]
        proj_name = data["proj_name"]
        p_type = data["p_type"]
        min_threshold = data["min_threshold"]

        if new_stock <= 0:
            df = df.drop(idx).reset_index(drop=True)
            log_event("Removed", part_num, part_name, f"Removed {amt_to_sub} units. Stock hit 0, item deleted.", project_under=proj_name, part_type=p_type)
            st.toast(f"🚨 ALERT: {part_name} has hit 0 and is completely out of stock!", icon="🚨")
            st.success("Item quantity dropped to 0 and has been removed from permanent inventory!")
        else:
            df.at[idx, 'Qty on Hand'] = new_stock
            log_event("Removed", part_num, part_name, f"Removed {amt_to_sub} units. Remaining: {new_stock}", project_under=proj_name, part_type=p_type)
            if new_stock <= min_threshold and min_threshold > 0:
                st.warning(f"⚠️ LOW STOCK ALERT: {part_name} is down to {new_stock} units!")
                st.toast(f"Low Stock Alert: {part_name} needs reordering!", icon="⚠️")
            else:
                st.success(f"Stock removed! Remaining units: {new_stock}")
        
        save_permanent_data(df)

    elif act["type"] == "ALTER":
        data = act["data"]
        idx = data["row_idx"]
        old_num = data["old_part_num"]
        new_num = data["updated_part_num"]
        
        # If Part Number changed, delete the record under the old Part Number from Supabase first
        if old_num != new_num:
            supabase.table("Inventory").delete().eq("Part Number", old_num).execute()

        df.at[idx, 'Part Number'] = new_num
        df.at[idx, 'Part Name'] = data["updated_name"]
        df.at[idx, 'Project Under'] = data["updated_project"]
        df.at[idx, 'Part Type'] = data["updated_type"]
        
        save_permanent_data(df)
        log_event("Altered", new_num, data["updated_name"], f"Updated Part Number ('{old_num}' ➔ '{new_num}'), Name ('{data['updated_name']}'), Project ('{data['updated_project']}'), Type ('{data['updated_type']}')", project_under=data["updated_project"], part_type=data["updated_type"])
        st.success("Part attributes successfully updated in database!")

    # Reset trigger flags
    st.session_state["pending_action"] = None
    st.session_state["pending_action_confirmed"] = False
    st.rerun()

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "Scan Search", 
    "Location Search",
    "Project Search",
    "Add Inventory", 
    "Take Inventory", 
    "Alter Part",
    "Change Part Location",
    "Log History"
])

# --- TAB 1: SCAN SEARCH ---
with tab1:
    st.header("Search Database by Part")
    search_query = st.text_input("Click here to SCAN a barcode, or TYPE a part name, number, or part type:", key="search_input").strip()
    
    if search_query:
        results = df[
            (df['Part Number'].astype(str) == search_query) | 
            (df['Part Name'].str.contains(search_query, case=False, na=False)) |
            (df['Part Type'].str.contains(search_query, case=False, na=False))
        ]
        
        if not results.empty:
            st.success(f"Found {len(results)} matching item(s):")
            for idx, row in results.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5, col6, col7 = st.columns([1.8, 2.2, 1.5, 1.2, 1.2, 1.5, 1.2])
                    
                    with col1:
                        st.caption("Part Number")
                        st.markdown(f"### `{row['Part Number']}`")
                    with col2:
                        st.caption("Part Name")
                        st.markdown(f"### {row['Part Name']}")
                    with col3:
                        st.caption("Part Type")
                        st.markdown(f"**{row['Part Type'] if row.get('Part Type') else 'N/A'}**")
                    with col4:
                        st.caption("Quantity")
                        st.markdown(f"### {int(row['Qty on Hand'])}")
                    with col5:
                        st.caption("Location")
                        st.markdown(f"### [{row['Location']}]")
                    with col6:
                        st.caption("Project Under")
                        st.markdown(f"### {row['Project Under']}")
                    with col7:
                        st.caption("Min Qty Limit")
                        st.markdown(f"### {int(row['Min Qty']) if pd.notna(row['Min Qty']) else 0}")
                    
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

# --- TAB 2: LOCATION SEARCH ---
with tab2:
    st.header("Search Database by Storage Location")
    loc_search_query = st.text_input("Enter Storage Location Code (e.g. C3, D4, F1):", key="loc_search_input").strip().upper()
    
    if loc_search_query:
        results = df[df['Location'].astype(str).str.upper() == loc_search_query]
        
        if not results.empty:
            st.success(f"Found {len(results)} item(s) stored in location [{loc_search_query}]:")
            for idx, row in results.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5, col6, col7 = st.columns([1.8, 2.2, 1.5, 1.2, 1.2, 1.5, 1.2])
                    
                    with col1:
                        st.caption("Part Number")
                        st.markdown(f"### `{row['Part Number']}`")
                    with col2:
                        st.caption("Part Name")
                        st.markdown(f"### {row['Part Name']}")
                    with col3:
                        st.caption("Part Type")
                        st.markdown(f"**{row['Part Type'] if row.get('Part Type') else 'N/A'}**")
                    with col4:
                        st.caption("Quantity")
                        st.markdown(f"### {int(row['Qty on Hand'])}")
                    with col5:
                        st.caption("Location")
                        st.markdown(f"### [{row['Location']}]")
                    with col6:
                        st.caption("Project Under")
                        st.markdown(f"### {row['Project Under']}")
                    with col7:
                        st.caption("Min Qty Limit")
                        st.markdown(f"### {int(row['Min Qty']) if pd.notna(row['Min Qty']) else 0}")
                    
                    barcode_img = generate_barcode_image(str(row['Part Number']))
                    if barcode_img:
                        st.image(barcode_img, caption=f"Visual Label Representation for {row['Part Number']}", width=300)
                        
                        st.download_button(
                            label=f"Download Printable Label for {row['Part Number']}",
                            data=barcode_img,
                            file_name=f"label_{row['Part Number']}.png",
                            mime="image/png",
                            key=f"dl_loc_{idx}"
                        )
                    st.markdown("---")
        else:
            st.warning(f"No items currently registered at location [{loc_search_query}].")

# --- TAB 3: PROJECT SEARCH ---
with tab3:
    st.header("Search Database by Project Under")
    
    col_p1, col_p2 = st.columns(2)
    
    known_projects = ["Select a Project..."] + sorted([p for p in df['Project Under'].dropna().astype(str).unique() if p.strip()])
    selected_proj_dropdown = col_p1.selectbox("Select from existing projects:", known_projects, key="proj_search_select")
    proj_search_query = col_p2.text_input("Or TYPE a project name:", key="proj_search_input").strip()
    
    target_project = ""
    if proj_search_query:
        target_project = proj_search_query
    elif selected_proj_dropdown != "Select a Project...":
        target_project = selected_proj_dropdown
        
    if target_project:
        results = df[df['Project Under'].str.contains(target_project, case=False, na=False)]
        
        if not results.empty:
            st.success(f"Found {len(results)} item(s) registered under project '{target_project}':")
            for idx, row in results.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5, col6, col7 = st.columns([1.8, 2.2, 1.5, 1.2, 1.2, 1.5, 1.2])
                    
                    with col1:
                        st.caption("Part Number")
                        st.markdown(f"### `{row['Part Number']}`")
                    with col2:
                        st.caption("Part Name")
                        st.markdown(f"### {row['Part Name']}")
                    with col3:
                        st.caption("Part Type")
                        st.markdown(f"**{row['Part Type'] if row.get('Part Type') else 'N/A'}**")
                    with col4:
                        st.caption("Quantity")
                        st.markdown(f"### {int(row['Qty on Hand'])}")
                    with col5:
                        st.caption("Location")
                        st.markdown(f"### [{row['Location']}]")
                    with col6:
                        st.caption("Project Under")
                        st.markdown(f"### {row['Project Under']}")
                    with col7:
                        st.caption("Min Qty Limit")
                        st.markdown(f"### {int(row['Min Qty']) if pd.notna(row['Min Qty']) else 0}")
                    
                    barcode_img = generate_barcode_image(str(row['Part Number']))
                    if barcode_img:
                        st.image(barcode_img, caption=f"Visual Label Representation for {row['Part Number']}", width=300)
                        
                        st.download_button(
                            label=f"Download Printable Label for {row['Part Number']}",
                            data=barcode_img,
                            file_name=f"label_{row['Part Number']}.png",
                            mime="image/png",
                            key=f"dl_proj_{idx}"
                        )
                    st.markdown("---")
        else:
            st.warning(f"No items currently registered under project '{target_project}'.")

# --- TAB 4: ADD INVENTORY WITH FILTERS ---
with tab4:
    st.header("Receive / Add Stock")
    
    col_f1, col_f2 = st.columns(2)
    existing_projects = ["All Projects"] + sorted(list(set(df['Project Under'].dropna().astype(str).unique())))
    existing_types = ["All Part Types"] + sorted([t for t in df['Part Type'].dropna().astype(str).unique() if t.strip()])
    
    selected_proj_add = col_f1.selectbox("Filter by Project Under:", existing_projects, key="add_filter_proj")
    selected_type_add = col_f2.selectbox("Filter by Part Type:", existing_types, key="add_filter_type")
    
    add_query = st.text_input("Scan or Type part to ADD stock:", key="add_input").strip()
    
    if add_query or selected_proj_add != "All Projects" or selected_type_add != "All Part Types":
        filtered_add = df.copy()
        
        if selected_proj_add != "All Projects":
            filtered_add = filtered_add[filtered_add['Project Under'] == selected_proj_add]
        if selected_type_add != "All Part Types":
            filtered_add = filtered_add[filtered_add['Part Type'] == selected_type_add]
        
        if add_query:
            results = filtered_add[
                (filtered_add['Part Number'].astype(str) == add_query) | 
                (filtered_add['Part Name'].str.contains(add_query, case=False, na=False))
            ]
        else:
            results = filtered_add

        if results.empty and add_query:
            st.info("Brand new item detected! Fill out the fields below to register it:")
            new_num = st.text_input("Part Number (This will become the barcode text):")
            new_name = st.text_input("Part Name:")
            
            known_types = sorted([t for t in df['Part Type'].dropna().astype(str).unique() if t.strip()])
            type_options = known_types + ["+ Add New Part Type"]
            
            selected_type_opt = st.selectbox("Part Type", options=type_options, key="new_part_type_select")
            if selected_type_opt == "+ Add New Part Type":
                new_type = st.text_input("Enter New Part Type Name:", key="new_part_type_custom").strip()
            else:
                new_type = selected_type_opt
                
            new_qty = st.number_input("Initial Quantity:", min_value=1, step=10, value=10)
            new_loc = st.text_input("Storage Location (Allowed: A1-A3, B1-B3, C1-C4, D1-D4, E1-E4, F1-F3, G1-G3):")
            new_proj = st.text_input("Project Under:")
            new_min_qty = st.number_input("Minimum Quantity Alert Threshold (Optional, set 0 for None):", min_value=0, step=10, value=0)
            
            if st.button("Save Brand New Item"):
                valid, formatted_loc = is_valid_location(new_loc)
                if not new_type:
                    st.error("Part Type is required and cannot be left blank.")
                elif not valid:
                    st.error("Invalid Location! Format must be Rack A-G (Shelves 1-3, or 1-4 for C, D, E). Examples: C4, F2")
                else:
                    st.session_state["pending_action"] = {
                        "type": "ADD_NEW",
                        "data": {
                            "Part Number": new_num, "Part Name": new_name,
                            "Part Type": new_type, "Qty on Hand": new_qty, 
                            "Location": formatted_loc, "Project Under": new_proj, "Min Qty": new_min_qty
                        }
                    }
                    st.rerun()
        elif not results.empty:
            options = [f"{row['Part Name']} | Type: {row['Part Type']} | Proj Under: {row['Project Under']} | Qty: {row['Qty on Hand']} | Loc: {row['Location']}" for idx, row in results.iterrows()]
            choice = st.selectbox("Select the correct item row to add stock to:", options, key="add_select")
            row_idx = results.index[options.index(choice)]
            
            amt_to_add = st.number_input("How many units are you adding?", min_value=1, step=10, value=10, key="add_amt")
            new_min_qty = st.number_input(f"Update Minimum Quantity Alert Level (Current: {df.at[row_idx, 'Min Qty']}):", min_value=0, step=10, value=int(df.at[row_idx, 'Min Qty']))
            
            if st.button("Confirm Addition"):
                st.session_state["pending_action"] = {
                    "type": "ADD_EXISTING",
                    "data": {
                        "row_idx": row_idx,
                        "amt_to_add": amt_to_add,
                        "new_min_qty": new_min_qty,
                        "part_name": df.at[row_idx, 'Part Name'],
                        "new_total": int(df.at[row_idx, 'Qty on Hand'] + amt_to_add)
                    }
                }
                st.rerun()

# --- TAB 5: TAKE INVENTORY WITH FILTERS ---
with tab5:
    st.header("Remove / Assemble Stock")
    
    col_f1, col_f2 = st.columns(2)
    existing_projects = ["All Projects"] + sorted(list(set(df['Project Under'].dropna().astype(str).unique())))
    existing_types = ["All Part Types"] + sorted([t for t in df['Part Type'].dropna().astype(str).unique() if t.strip()])
    
    selected_proj_take = col_f1.selectbox("Filter by Project Under:", existing_projects, key="take_filter_proj")
    selected_type_take = col_f2.selectbox("Filter by Part Type:", existing_types, key="take_filter_type")
    
    take_query = st.text_input("Scan or Type part to TAKE stock:", key="take_input").strip()
    
    if take_query or selected_proj_take != "All Projects" or selected_type_take != "All Part Types":
        filtered_take = df.copy()
        
        if selected_proj_take != "All Projects":
            filtered_take = filtered_take[filtered_take['Project Under'] == selected_proj_take]
        if selected_type_take != "All Part Types":
            filtered_take = filtered_take[filtered_take['Part Type'] == selected_type_take]
            
        if take_query:
            results = filtered_take[
                (filtered_take['Part Number'].astype(str) == take_query) | 
                (filtered_take['Part Name'].str.contains(take_query, case=False, na=False))
            ]
        else:
            results = filtered_take
        
        if results.empty:
            st.error("No parts found matching selected filters or query.")
        else:
            options = [f"{row['Part Name']} | Type: {row['Part Type']} | Proj Under: {row['Project Under']} | Qty: {row['Qty on Hand']} | Loc: {row['Location']}" for idx, row in results.iterrows()]
            choice = st.selectbox("Select the item row you are pulling from:", options, key="take_select")
            row_idx = results.index[options.index(choice)]
            
            amt_to_sub = st.number_input("How many units are you taking for assembly?", min_value=1, step=10, value=10, key="take_amt")
            if st.button("Confirm Removal"):
                current_stock = df.at[row_idx, 'Qty on Hand']
                st.session_state["pending_action"] = {
                    "type": "TAKE",
                    "data": {
                        "row_idx": row_idx,
                        "amt_to_sub": amt_to_sub,
                        "new_stock": current_stock - amt_to_sub,
                        "part_num": df.at[row_idx, 'Part Number'],
                        "part_name": df.at[row_idx, 'Part Name'],
                        "proj_name": df.at[row_idx, 'Project Under'],
                        "p_type": df.at[row_idx, 'Part Type'],
                        "min_threshold": df.at[row_idx, 'Min Qty']
                    }
                }
                st.rerun()

# --- TAB 6: ALTER PART ---
with tab6:
    st.header("Alter Part Attributes")
    alter_query = st.text_input("Scan or Type part to ALTER:", key="alter_input").strip()
    
    if alter_query:
        results = df[
            (df['Part Number'].astype(str) == alter_query) | 
            (df['Part Name'].str.contains(alter_query, case=False, na=False))
        ]
        
        if results.empty:
            st.error("Part not found.")
        else:
            options = [f"{row['Part Number']} | {row['Part Name']} | Proj Under: {row['Project Under']} | Loc: {row['Location']}" for idx, row in results.iterrows()]
            choice = st.selectbox("Select the exact item to edit:", options, key="alter_select")
            row_idx = results.index[options.index(choice)]
            
            st.subheader(f"Editing Part: {df.at[row_idx, 'Part Number']}")
            
            updated_part_num = st.text_input("Part Number:", value=str(df.at[row_idx, 'Part Number']))
            updated_name = st.text_input("Part Name:", value=str(df.at[row_idx, 'Part Name']))
            
            col_a1, col_a2 = st.columns(2)
            updated_project = col_a1.text_input("Project Under:", value=str(df.at[row_idx, 'Project Under']))
            
            current_type = str(df.at[row_idx, 'Part Type']) if pd.notna(df.at[row_idx, 'Part Type']) else ""
            known_types = sorted([t for t in df['Part Type'].dropna().astype(str).unique() if t.strip()])
            
            if current_type and current_type not in known_types:
                known_types.append(current_type)
            
            type_options = known_types + ["+ Add New Part Type"]
            
            default_index = type_options.index(current_type) if current_type in type_options else 0
            selected_type_opt = col_a2.selectbox("Part Type", options=type_options, index=default_index, key="alter_part_type_select")
            
            if selected_type_opt == "+ Add New Part Type":
                updated_type = col_a2.text_input("Enter New Part Type Name:", key="alter_part_type_custom").strip()
            else:
                updated_type = selected_type_opt
            
            if st.button("Save Altered Attributes"):
                if not updated_part_num.strip():
                    st.error("Part Number cannot be blank.")
                elif not updated_type:
                    st.error("Part Type is required and cannot be left blank.")
                else:
                    st.session_state["pending_action"] = {
                        "type": "ALTER",
                        "data": {
                            "row_idx": row_idx,
                            "old_part_num": str(df.at[row_idx, 'Part Number']),
                            "updated_part_num": updated_part_num.strip(),
                            "updated_name": updated_name,
                            "updated_project": updated_project,
                            "updated_type": updated_type
                        }
                    }
                    st.rerun()

# --- TAB 7: CHANGE LOCATION ---
with tab7:
    st.header("Move Parts to a New Location")
    loc_query = st.text_input("Scan or Type part to change its LOCATION:", key="loc_input").strip()
    
    if loc_query:
        results = df[
            (df['Part Number'].astype(str) == loc_query) | 
            (df['Part Name'].str.contains(loc_query, case=False, na=False))
        ]
        
        if results.empty:
            st.error("Part not found.")
        else:
            options = [f"{row['Part Name']} | Project Under: {row['Project Under']} | Current Location: {row['Location']}" for idx, row in results.iterrows()]
            choice = st.selectbox("Select the item listing you want to move:", options, key="loc_select")
            row_idx = results.index[options.index(choice)]
            
            new_location = st.text_input(f"Enter new location code (Allowed: A1-A3, B1-B3, C1-C4, D1-D4, E1-E4, F1-F3, G1-G3):")
            if st.button("Update Location"):
                valid, formatted_loc = is_valid_location(new_location)
                if not valid:
                    st.error("Invalid Location! Must be Rack A-G (Shelves 1-3, or 1-4 for C, D, E). Examples: C4, F1")
                else:
                    old_loc = df.at[row_idx, 'Location']
                    part_num = df.at[row_idx, 'Part Number']
                    part_name = df.at[row_idx, 'Part Name']
                    proj_name = df.at[row_idx, 'Project Under']
                    p_type = df.at[row_idx, 'Part Type']
                    
                    df.at[row_idx, 'Location'] = formatted_loc
                    save_permanent_data(df)
                    log_event("Moved", part_num, part_name, f"Moved from {old_loc} to {formatted_loc}", project_under=proj_name, part_type=p_type)
                    st.success(f"Location permanently updated to [{formatted_loc}]!")
                    st.rerun()

# --- TAB 8: LOG HISTORY WITH FILTERS ---
with tab8:
    st.header("Activity Log History")
    log_df = load_logs()
    if log_df.empty:
        st.info("No activity logged yet.")
    else:
        col_l1, col_l2, col_l3 = st.columns(3)
        
        action_filter = col_l1.selectbox("Filter by Action:", ["All", "Added", "Removed", "Moved", "Altered"])
        log_proj_filter = col_l2.selectbox("Filter by Project Under:", ["All Projects"] + sorted(list(set(log_df['Project Under'].dropna().astype(str).unique()))))
        log_type_filter = col_l3.selectbox("Filter by Part Type:", ["All Part Types"] + sorted([t for t in log_df['Part Type'].dropna().astype(str).unique() if t.strip()]))
        
        filtered_logs = log_df.copy()
        if action_filter != "All":
            filtered_logs = filtered_logs[filtered_logs['Action'] == action_filter]
        if log_proj_filter != "All Projects":
            filtered_logs = filtered_logs[filtered_logs['Project Under'] == log_proj_filter]
        if log_type_filter != "All Part Types":
            filtered_logs = filtered_logs[filtered_logs['Part Type'] == log_type_filter]
            
        st.dataframe(filtered_logs.iloc[::-1], use_container_width=True)

st.sidebar.header("Live Inventory Grid View")
styled_df = df.style.apply(highlight_shortages, axis=1)
st.sidebar.dataframe(styled_df, use_container_width=True)

# --- Permanent Legacy Footer ---
st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div style='text-align: center; color: gray; font-size: 0.8em;'>
        <b>Panel Shop Inventory System v2.0</b><br>
        Designed & Built by <b>Zhou Czornoba</b><br>
        Co-op Term May-August 2026
    </div>
    """, 
    unsafe_allow_html=True
)
