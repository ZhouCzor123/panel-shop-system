import streamlit as st
import pandas as pd
from supabase import create_client, Client
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO
import re
import pytz
import streamlit.components.v1 as components

PASSWORD = "PanelShopSecure2026"

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- PAGE SETUP & CUSTOM SCROLLBAR CSS ---
st.set_page_config(
    page_title="Panel Shop Inventory System", 
    page_icon="BlackMcDonald_Logo.webp", 
    layout="wide"
)

# Custom CSS to force visible, styled scrollbars for vertical and horizontal scrolling
st.markdown("""
    <style>
    /* Force visible scrollbars across main page and sidebar */
    ::-webkit-scrollbar {
        width: 12px !important;
        height: 12px !important;
    }
    ::-webkit-scrollbar-track {
        background: #1e1e1e !important;
        border-radius: 6px !important;
    }
    ::-webkit-scrollbar-thumb {
        background: #4a4a4a !important;
        border-radius: 6px !important;
        border: 2px solid #1e1e1e !important;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #ff4b4b !important;
    }
    
    /* Ensure content containers scroll cleanly vertically and horizontally */
    .stMainBlockContainer, [data-testid="stSidebarContent"] {
        overflow-x: auto !important;
        overflow-y: auto !important;
    }
    
    /* Dataframe table containers scroll styling */
    [data-testid="stDataFrame"] > div {
        overflow-x: auto !important;
        overflow-y: auto !important;
        max-height: 70vh !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- DATABASE LOADERS ---
def load_permanent_data():
    try:
        response = supabase.table("Inventory").select("*").execute()
        df = pd.DataFrame(response.data)
        if df.empty:
            return pd.DataFrame(columns=['id', 'Part Number', 'Part Name', 'Part Type', 'Qty on Hand', 'Location', 'Project Under', 'Min Qty', 'PO Number'])
        
        if 'Project' in df.columns and 'Project Under' not in df.columns:
            df.rename(columns={'Project': 'Project Under'}, inplace=True)
            
        df = df[df['Part Number'] != "___DUMMY___"]
        df['Part Number'] = df['Part Number'].astype(str)
        if 'Part Type' not in df.columns:
            df['Part Type'] = ""
        if 'Min Qty' not in df.columns:
            df['Min Qty'] = 0
        if 'PO Number' not in df.columns:
            df['PO Number'] = ""
        return df
    except Exception as e:
        st.error(f"Error loading inventory: {e}")
        return pd.DataFrame(columns=['id', 'Part Number', 'Part Name', 'Part Type', 'Qty on Hand', 'Location', 'Project Under', 'Min Qty', 'PO Number'])

def load_disregarded_items():
    try:
        response = supabase.table("Disregarded_Items").select("*").execute()
        df = pd.DataFrame(response.data)
        if df.empty:
            return pd.DataFrame(columns=['Part Number', 'Project Under', 'Location'])
        return df
    except Exception:
        return pd.DataFrame(columns=['Part Number', 'Project Under', 'Location'])

def delete_inventory_row(row_id, part_num, project_under):
    try:
        if row_id is not None and pd.notna(row_id):
            supabase.table("Inventory").delete().eq("id", row_id).execute()
        else:
            supabase.table("Inventory").delete().eq("Part Number", str(part_num)).eq("Project Under", str(project_under)).execute()
            
        supabase.table("Disregarded_Items").insert({
            "Part Number": str(part_num),
            "Project Under": str(project_under)
        }).execute()
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error removing item: {e}")

def load_logs():
    try:
        response = supabase.table("Logs").select("*").execute()
        df = pd.DataFrame(response.data)
        if df.empty:
            return pd.DataFrame(columns=['Timestamp', 'Action', 'Part Number', 'Part Name', 'Project Under', 'Part Type', 'Details'])
        
        if 'id' in df.columns:
            df = df.drop(columns=['id'])
        if 'Project' in df.columns and 'Project Under' not in df.columns:
            df.rename(columns={'Project': 'Project Under'}, inplace=True)
            
        df = df[df['Action'] != "___DUMMY___"]
        df['Part Number'] = df['Part Number'].astype(str)
        for col in ['Project Under', 'Part Type', 'PO Number']:
            if col not in df.columns:
                df[col] = ""
        return df
    except Exception:
        return pd.DataFrame(columns=['Timestamp', 'Action', 'Part Number', 'Part Name', 'Project Under', 'Part Type', 'Details'])

def log_event(action, part_num, part_name, details, project_under="", part_type=""):
    try:
        eastern_tz = pytz.timezone('America/Toronto')
        current_time = pd.Timestamp.now(tz=eastern_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        supabase.table("Logs").insert({
            'Timestamp': current_time,
            'Action': str(action),
            'Part Number': str(part_num),
            'Part Name': str(part_name),
            'Project Under': str(project_under),
            'Part Type': str(part_type),
            'Details': str(details)
        }).execute()
    except Exception as e:
        st.error(f"Error logging event: {e}")

def is_valid_location(loc_string):
    clean_loc = loc_string.strip().upper()
    pattern = r"^([C-E][1-4]|[A-B][1-3]|[F-I][1-3])$"
    return bool(re.match(pattern, clean_loc)), clean_loc

def get_location_category(loc_string):
    clean_loc = loc_string.strip().upper()
    if re.match(r"^[G-I]", clean_loc):
        return "Upstairs"
    elif re.match(r"^[A-F]", clean_loc):
        return "Downstairs"
    return "Unknown"

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

# Strict Space, Dash, Slash & Case Insensitive Normalization
def normalize_str(val):
    if pd.isna(val):
        return ""
    return re.sub(r'[\s\-_/\\.]+', '', str(val)).lower()

def fuzzy_search_df(dataframe, query):
    if not query:
        return pd.DataFrame()
    norm_query = normalize_str(query)
    
    mask = (
        dataframe['Part Number'].apply(normalize_str).str.contains(norm_query, na=False) |
        dataframe['Part Name'].apply(normalize_str).str.contains(norm_query, na=False) |
        dataframe['Part Type'].apply(normalize_str).str.contains(norm_query, na=False) |
        dataframe['Project Under'].apply(normalize_str).str.contains(norm_query, na=False) |
        dataframe['PO Number'].apply(normalize_str).str.contains(norm_query, na=False)
    )
    return dataframe[mask]

def apply_category_filters(dataframe, proj_filter, type_filter):
    filtered_df = dataframe.copy()
    if proj_filter and proj_filter != "All Projects":
        filtered_df = filtered_df[filtered_df['Project Under'] == proj_filter]
    if type_filter and type_filter != "All Part Types":
        filtered_df = filtered_df[filtered_df['Part Type'] == type_filter]
    return filtered_df

# --- STATE-BASED VERIFICATION DIALOGS ---
if "pending_action" not in st.session_state:
    st.session_state["pending_action"] = None

@st.dialog("Confirm Action")
def show_confirmation_dialog():
    action_data = st.session_state.get("pending_action")
    if not action_data:
        st.rerun()

    action_type = action_data.get("type")

    if action_type == "add":
        is_new = action_data["is_new"]
        pnum, pname = action_data["pnum"], action_data["pname"]
        amt, loc, proj = action_data["amt"], action_data["loc"], action_data["proj"]
        ptype, po, min_qty = action_data["ptype"], action_data["po"], action_data["min_qty"]
        current_qty = action_data.get("current_qty", 0)
        target_id = action_data.get("target_id")

        if is_new:
            st.write(f"Are you sure you want to register brand new item **{pname}** (`{pnum}`)?")
            st.write(f"- **Initial Quantity:** {amt}")
            st.write(f"- **Location:** {loc}")
            st.write(f"- **Project:** {proj}")
        else:
            st.write(f"Are you sure you want to add **{amt}** units to **{pname}** (`{pnum}`)?")
            st.write(f"- **Current Stock:** {current_qty}")
            st.write(f"- **New Total Quantity:** {current_qty + amt}")

        col1, col2 = st.columns(2)
        if col1.button("Yes, Confirm Add", type="primary"):
            if is_new:
                supabase.table("Inventory").insert({
                    "Part Number": str(pnum),
                    "Part Name": str(pname),
                    "Part Type": str(ptype),
                    "Qty on Hand": int(amt),
                    "Location": str(loc),
                    "Project Under": str(proj),
                    "PO Number": str(po),
                    "Min Qty": int(min_qty)
                }).execute()
                log_event("Added", pnum, pname, f"Registered new item. Initial Qty: {amt} at {loc}. PO#: {po}", project_under=proj, part_type=ptype)
            else:
                query = supabase.table("Inventory").update({
                    "Qty on Hand": current_qty + amt,
                    "Min Qty": int(min_qty),
                    "Location": str(loc),
                    "Project Under": str(proj)
                })
                if target_id is not None and pd.notna(target_id):
                    query = query.eq("id", target_id)
                else:
                    query = query.eq("Part Number", str(pnum)).eq("Location", str(loc)).eq("Project Under", str(proj))
                query.execute()
                log_event("Added", pnum, pname, f"Added {amt} units. New Total: {current_qty + amt}.", project_under=proj, part_type=ptype)
            
            st.session_state["pending_action"] = None
            st.success("Stock updated permanently!")
            st.rerun()

        if col2.button("No, Cancel"):
            st.session_state["pending_action"] = None
            st.rerun()

    elif action_type == "take":
        pnum, pname = action_data["pnum"], action_data["pname"]
        amt, loc, proj = action_data["amt"], action_data["loc"], action_data["proj"]
        ptype, current_qty, min_qty = action_data["ptype"], action_data["current_qty"], action_data["min_qty"]
        target_id = action_data.get("target_id")
        new_stock = current_qty - amt

        st.write(f"Are you sure you want to remove **{amt}** units of **{pname}** (`{pnum}`)?")
        st.write(f"- **Current Stock:** {current_qty}")
        st.write(f"- **Remaining Stock After Removal:** {max(0, new_stock)}")

        col1, col2 = st.columns(2)
        if col1.button("Yes, Confirm Removal", type="primary"):
            query = supabase.table("Inventory").update({"Qty on Hand": max(0, new_stock)})
            if target_id is not None and pd.notna(target_id):
                query = query.eq("id", target_id)
            else:
                query = query.eq("Part Number", str(pnum)).eq("Location", str(loc)).eq("Project Under", str(proj))
            query.execute()

            if new_stock <= 0:
                log_event("Removed", pnum, pname, f"Removed {amt} units. Stock hit 0.", project_under=proj, part_type=ptype)
                st.toast(f"🚨 ALERT: {pname} has hit 0 and is completely out of stock!", icon="🚨")
            else:
                log_event("Removed", pnum, pname, f"Removed {amt} units. Remaining: {new_stock}", project_under=proj, part_type=ptype)
                if new_stock <= min_qty and min_qty > 0:
                    st.warning(f"⚠️ LOW STOCK ALERT: {pname} is down to {new_stock} units!")
            
            st.session_state["pending_action"] = None
            st.success("Stock removed permanently!")
            st.rerun()

        if col2.button("No, Cancel"):
            st.session_state["pending_action"] = None
            st.rerun()

    elif action_type == "alter":
        orig_pnum = action_data["orig_pnum"]
        new_name, new_proj = action_data["new_name"], action_data["new_proj"]
        new_po, new_type = action_data["new_po"], action_data["new_type"]
        target_id = action_data.get("target_id")

        st.write(f"Are you sure you want to update attributes for **{new_name}** (`{orig_pnum}`)?")
        st.write(f"- **Project Under:** {new_proj}")
        st.write(f"- **PO Number:** {new_po}")
        st.write(f"- **Part Type:** {new_type}")

        col1, col2 = st.columns(2)
        if col1.button("Yes, Save Changes", type="primary"):
            query = supabase.table("Inventory").update({
                "Part Name": str(new_name),
                "Project Under": str(new_proj),
                "PO Number": str(new_po),
                "Part Type": str(new_type)
            })
            if target_id is not None and pd.notna(target_id):
                query = query.eq("id", target_id)
            else:
                query = query.eq("Part Number", str(orig_pnum))
            query.execute()
            
            log_event("Altered", orig_pnum, new_name, f"Updated Attributes (PO#: {new_po}).", project_under=new_proj, part_type=new_type)
            st.session_state["pending_action"] = None
            st.success("Part attributes successfully updated!")
            st.rerun()

        if col2.button("No, Cancel"):
            st.session_state["pending_action"] = None
            st.rerun()

    elif action_type == "disregard":
        disregarded_rows = action_data["rows"]
        st.write("Are you sure you want to disregard and permanently remove the following out-of-stock item(s)?")
        for _, r in disregarded_rows.iterrows():
            st.write(f"- **{r['Part Name']}** (`{r['Part Number']}`) [Project: {r['Project Under']}] (ID: {r.get('id', 'N/A')})")

        col1, col2 = st.columns(2)
        if col1.button("Yes, Confirm Disregard", type="primary"):
            for _, r in disregarded_rows.iterrows():
                row_id = r.get('id') if 'id' in r and pd.notna(r['id']) else None
                delete_inventory_row(row_id, r['Part Number'], r['Project Under'])
                log_event("Disregarded", r['Part Number'], r['Part Name'], f"Disregarded row ID: {row_id}", project_under=r['Project Under'])
            st.session_state["pending_action"] = None
            st.success("Item(s) disregarded and deleted from inventory!")
            st.rerun()

        if col2.button("No, Cancel"):
            st.session_state["pending_action"] = None
            st.rerun()

# Trigger confirmation dialog if pending action exists
if st.session_state.get("pending_action"):
    show_confirmation_dialog()

# --- AUTHENTICATION ---
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

st.title("Panel Shop Inventory System")
df = load_permanent_data()
active_df = df.copy()

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "Scan Search", 
    "Location Search",
    "Project & PO Search",
    "Add Inventory", 
    "Take Inventory", 
    "Alter Part",
    "Change Part Location",
    "Log History"
])

# --- TAB 1: SCAN SEARCH ---
with tab1:
    st.header("Search Database by Part")
    search_query = st.text_input("Click here to SCAN a barcode, or TYPE part details (Name, Number, Type, PO#):", key="search_input").strip()
    
    if search_query:
        results = fuzzy_search_df(active_df, search_query)
        
        if not results.empty:
            st.success(f"Found {len(results)} matching item(s):")
            for idx, row in results.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5, col6, col7 = st.columns([1.8, 2.2, 1.3, 1.0, 1.5, 1.3, 1.2])
                    
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
                        loc_cat = get_location_category(str(row['Location']))
                        st.caption("Location")
                        st.markdown(f"### [{row['Location']}] *({loc_cat})*")
                    with col6:
                        st.caption("Project / PO#")
                        st.markdown(f"**Proj:** {row['Project Under']}\n\n**PO#:** {row['PO Number'] if row.get('PO Number') else 'N/A'}")
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
            st.error(f"No active parts match your search for '{search_query}'.")

# --- TAB 2: LOCATION SEARCH ---
with tab2:
    st.header("Search Database by Storage Location")
    
    col_l1, col_l2 = st.columns(2)
    selected_floor = col_l1.selectbox("Filter by Floor Category:", ["All Floors", "Downstairs (A-F Sections)", "Upstairs (G-I Sections)"], key="floor_select")
    loc_search_query = col_l2.text_input("Or TYPE Specific Location Code (e.g. C3, G1, H2):", key="loc_search_input").strip().upper()
    
    results = active_df.copy()
    
    if selected_floor == "Downstairs (A-F Sections)":
        results = results[results['Location'].astype(str).str.upper().str.match(r"^[A-F]")]
    elif selected_floor == "Upstairs (G-I Sections)":
        results = results[results['Location'].astype(str).str.upper().str.match(r"^[G-I]")]
        
    if loc_search_query:
        norm_loc = normalize_str(loc_search_query)
        results = results[results['Location'].apply(normalize_str) == norm_loc]
        
    if not results.empty:
        st.success(f"Found {len(results)} item(s) in selected location filter:")
        for idx, row in results.iterrows():
            with st.container():
                col1, col2, col3, col4, col5, col6, col7 = st.columns([1.8, 2.2, 1.3, 1.0, 1.5, 1.3, 1.2])
                
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
                    loc_cat = get_location_category(str(row['Location']))
                    st.caption("Location")
                    st.markdown(f"### [{row['Location']}] *({loc_cat})*")
                with col6:
                    st.caption("Project / PO#")
                    st.markdown(f"**Proj:** {row['Project Under']}\n\n**PO#:** {row['PO Number'] if row.get('PO Number') else 'N/A'}")
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
        st.warning("No items found matching the selected location filters.")

# --- TAB 3: PROJECT & PO SEARCH ---
with tab3:
    st.header("Search Database by Project Under or PO Number")
    
    col_p1, col_p2 = st.columns(2)
    col_po1, col_po2 = st.columns(2)
    
    known_projects = ["Select a Project..."] + sorted([p for p in active_df['Project Under'].dropna().astype(str).unique() if p.strip()])
    selected_proj_dropdown = col_p1.selectbox("Select from existing projects:", known_projects, key="proj_search_select")
    proj_search_query = col_p2.text_input("Or TYPE a project name:", key="proj_search_input").strip()
    
    known_pos = ["Select a PO Number..."] + sorted([po for po in active_df['PO Number'].dropna().astype(str).unique() if po.strip()])
    selected_po_dropdown = col_po1.selectbox("Select from existing PO numbers:", known_pos, key="po_search_select")
    po_search_query = col_po2.text_input("Or TYPE a PO number:", key="po_search_input").strip()
    
    results = active_df.copy()
    has_filter = False
    
    if proj_search_query:
        norm_p = normalize_str(proj_search_query)
        results = results[results['Project Under'].apply(normalize_str).str.contains(norm_p, na=False)]
        has_filter = True
    elif selected_proj_dropdown != "Select a Project...":
        results = results[results['Project Under'] == selected_proj_dropdown]
        has_filter = True
        
    if po_search_query:
        norm_po = normalize_str(po_search_query)
        results = results[results['PO Number'].apply(normalize_str).str.contains(norm_po, na=False)]
        has_filter = True
    elif selected_po_dropdown != "Select a PO Number...":
        results = results[results['PO Number'].astype(str) == selected_po_dropdown]
        has_filter = True
        
    if has_filter:
        if not results.empty:
            st.success(f"Found {len(results)} matching item(s):")
            for idx, row in results.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5, col6, col7 = st.columns([1.8, 2.2, 1.3, 1.0, 1.5, 1.3, 1.2])
                    
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
                        loc_cat = get_location_category(str(row['Location']))
                        st.caption("Location")
                        st.markdown(f"### [{row['Location']}] *({loc_cat})*")
                    with col6:
                        st.caption("Project / PO#")
                        st.markdown(f"**Proj:** {row['Project Under']}\n\n**PO#:** {row['PO Number'] if row.get('PO Number') else 'N/A'}")
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
            st.warning("No items currently registered matching selected Project or PO criteria.")

# --- TAB 4: ADD INVENTORY ---
with tab4:
    st.header("Receive / Add Stock")
    
    col_f1, col_f2 = st.columns(2)
    existing_projects = ["All Projects"] + sorted(list(set(active_df['Project Under'].dropna().astype(str).unique())))
    existing_types = ["All Part Types"] + sorted([t for t in active_df['Part Type'].dropna().astype(str).unique() if t.strip()])
    
    selected_proj_add = col_f1.selectbox("Filter by Project Under:", existing_projects, key="add_filter_proj")
    selected_type_add = col_f2.selectbox("Filter by Part Type:", existing_types, key="add_filter_type")
    
    filtered_add_pool = apply_category_filters(active_df, selected_proj_add, selected_type_add)
    add_query = st.text_input("Type any part number, name, or character fragment to ADD stock:", key="add_input").strip()
    
    show_new_form = False
    
    if add_query:
        results = fuzzy_search_df(filtered_add_pool, add_query)
        if results.empty:
            global_check = fuzzy_search_df(active_df, add_query)
            if not global_check.empty:
                st.warning(f"No match found under current filters ('{selected_proj_add}' / '{selected_type_add}'), but found matching item(s) in main database:")
                results = global_check
            else:
                st.warning(f"No existing items found matching '{add_query}'. Fill out the form below to register it as a brand new item:")
                show_new_form = True
    else:
        results = filtered_add_pool
        if st.checkbox("Register a Brand New Item"):
            show_new_form = True

    if show_new_form:
        st.info("Fill out the fields below to register a brand new item:")
        
        new_num = st.text_input("Part Number:", value=add_query)
        new_name = st.text_input("Part Name:")
        
        known_types = sorted([t for t in active_df['Part Type'].dropna().astype(str).unique() if t.strip()])
        type_options = known_types + ["+ Add New Part Type"]
        
        selected_type_opt = st.selectbox("Part Type", options=type_options, key="new_part_type_select")
        if selected_type_opt == "+ Add New Part Type":
            new_type = st.text_input("Enter New Part Type Name:", key="new_part_type_custom").strip()
        else:
            new_type = selected_type_opt
            
        new_qty = st.number_input("Initial Quantity:", min_value=1, step=10, value=10)
        new_loc = st.text_input("Storage Location (Downstairs: A1-F3, Upstairs: G1-I3):")
        
        col_n1, col_n2 = st.columns(2)
        new_proj = col_n1.text_input("Project Under:")
        new_po = col_n2.text_input("PO Number Ordered Under (Optional):")
        
        new_min_qty = st.number_input("Minimum Quantity Alert Threshold (Optional, set 0 for None):", min_value=0, step=10, value=0)
        
        if st.button("Save Brand New Item"):
            valid, formatted_loc = is_valid_location(new_loc)
            
            if not new_num.strip():
                st.error("Part Number is required.")
            elif not new_type:
                st.error("Part Type is required.")
            elif not valid:
                st.error("Invalid Location! Allowed Downstairs: A1-A3, B1-B3, C1-C4, D1-D4, E1-E4, F1-F3 | Allowed Upstairs: G1-G3, H1-H3, I1-I3")
            else:
                st.session_state["pending_action"] = {
                    "type": "add",
                    "is_new": True,
                    "pnum": new_num,
                    "pname": new_name,
                    "amt": new_qty,
                    "loc": formatted_loc,
                    "proj": new_proj,
                    "ptype": new_type,
                    "po": new_po,
                    "min_qty": new_min_qty
                }
                st.rerun()

    elif not results.empty and add_query:
        st.success(f"Found {len(results)} matching item(s):")
        options = [f"{row['Part Name']} (#{row['Part Number']}) | Type: {row['Part Type']} | Proj: {row['Project Under']} | PO#: {row['PO Number']} | Qty: {row['Qty on Hand']} | Loc: {row['Location']} (ID: {row.get('id', 'N/A')})" for idx, row in results.iterrows()]
        choice = st.selectbox("Select the exact item row to add stock to:", options, key="add_select")
        row_idx = results.index[options.index(choice)]
        
        amt_to_add = st.number_input("How many units are you adding?", min_value=1, step=10, value=10, key="add_amt")
        new_min_qty = st.number_input(f"Update Minimum Quantity Alert Level (Current: {active_df.at[row_idx, 'Min Qty']}):", min_value=0, step=10, value=int(active_df.at[row_idx, 'Min Qty']))
        
        if st.button("Confirm Addition"):
            target_id = active_df.at[row_idx, 'id'] if 'id' in active_df.columns else None
            target_pnum = active_df.at[row_idx, 'Part Number']
            target_pname = active_df.at[row_idx, 'Part Name']
            target_loc = active_df.at[row_idx, 'Location']
            target_proj = active_df.at[row_idx, 'Project Under']
            target_po = active_df.at[row_idx, 'PO Number']
            target_ptype = active_df.at[row_idx, 'Part Type']
            current_qty = int(active_df.at[row_idx, 'Qty on Hand'])
            
            st.session_state["pending_action"] = {
                "type": "add",
                "is_new": False,
                "target_id": target_id,
                "pnum": target_pnum,
                "pname": target_pname,
                "amt": amt_to_add,
                "loc": target_loc,
                "proj": target_proj,
                "ptype": target_ptype,
                "po": target_po,
                "current_qty": current_qty,
                "min_qty": new_min_qty
            }
            st.rerun()

# --- TAB 5: TAKE INVENTORY ---
with tab5:
    st.header("Remove / Assemble Stock")
    
    col_f1, col_f2 = st.columns(2)
    existing_projects = ["All Projects"] + sorted(list(set(active_df['Project Under'].dropna().astype(str).unique())))
    existing_types = ["All Part Types"] + sorted([t for t in active_df['Part Type'].dropna().astype(str).unique() if t.strip()])
    
    selected_proj_take = col_f1.selectbox("Filter by Project Under:", existing_projects, key="take_filter_proj")
    selected_type_take = col_f2.selectbox("Filter by Part Type:", existing_types, key="take_filter_type")
    
    filtered_take_pool = apply_category_filters(active_df, selected_proj_take, selected_type_take)
    take_query = st.text_input("Type any part number, name, or character fragment to TAKE stock:", key="take_input").strip()
    
    if take_query:
        results = fuzzy_search_df(filtered_take_pool, take_query)
    else:
        results = filtered_take_pool
    
    if results.empty:
        st.warning("No parts found matching selected search query or filters.")
    else:
        options = [f"{row['Part Name']} (#{row['Part Number']}) | Type: {row['Part Type']} | Proj: {row['Project Under']} | PO#: {row['PO Number']} | Qty: {row['Qty on Hand']} | Loc: {row['Location']} (ID: {row.get('id', 'N/A')})" for idx, row in results.iterrows()]
        choice = st.selectbox("Select the exact item row you are pulling stock from:", options, key="take_select")
        row_idx = results.index[options.index(choice)]
        
        amt_to_sub = st.number_input("How many units are you taking for assembly?", min_value=1, step=10, value=10, key="take_amt")
        if st.button("Confirm Removal"):
            target_id = active_df.at[row_idx, 'id'] if 'id' in active_df.columns else None
            current_stock = int(active_df.at[row_idx, 'Qty on Hand'])
            part_num = active_df.at[row_idx, 'Part Number']
            part_name = active_df.at[row_idx, 'Part Name']
            proj_name = active_df.at[row_idx, 'Project Under']
            loc_name = active_df.at[row_idx, 'Location']
            p_type = active_df.at[row_idx, 'Part Type']
            min_threshold = int(active_df.at[row_idx, 'Min Qty'])
            
            st.session_state["pending_action"] = {
                "type": "take",
                "target_id": target_id,
                "pnum": part_num,
                "pname": part_name,
                "amt": amt_to_sub,
                "loc": loc_name,
                "proj": proj_name,
                "ptype": p_type,
                "current_qty": current_stock,
                "min_qty": min_threshold
            }
            st.rerun()

# --- TAB 6: ALTER PART ---
with tab6:
    st.header("Alter Part Attributes")
    
    col_f1, col_f2 = st.columns(2)
    existing_projects = ["All Projects"] + sorted(list(set(active_df['Project Under'].dropna().astype(str).unique())))
    existing_types = ["All Part Types"] + sorted([t for t in active_df['Part Type'].dropna().astype(str).unique() if t.strip()])
    
    selected_proj_alter = col_f1.selectbox("Filter by Project Under:", existing_projects, key="alter_filter_proj")
    selected_type_alter = col_f2.selectbox("Filter by Part Type:", existing_types, key="alter_filter_type")
    
    filtered_alter_pool = apply_category_filters(active_df, selected_proj_alter, selected_type_alter)
    alter_query = st.text_input("Type any part number, name, or character fragment to ALTER:", key="alter_input").strip()
    
    if alter_query:
        results = fuzzy_search_df(filtered_alter_pool, alter_query)
    else:
        results = filtered_alter_pool
        
    if results.empty:
        st.error("No parts found matching your query or filters.")
    else:
        options = [f"{row['Part Name']} (#{row['Part Number']}) | Proj: {row['Project Under']} | PO#: {row['PO Number']} | Loc: {row['Location']} (ID: {row.get('id', 'N/A')})" for idx, row in results.iterrows()]
        choice = st.selectbox("Select the exact item to edit:", options, key="alter_select")
        row_idx = results.index[options.index(choice)]
        
        st.subheader(f"Editing Part: {active_df.at[row_idx, 'Part Number']}")
        
        target_id = active_df.at[row_idx, 'id'] if 'id' in active_df.columns else None
        orig_pnum = active_df.at[row_idx, 'Part Number']
        orig_loc = active_df.at[row_idx, 'Location']
        orig_proj = active_df.at[row_idx, 'Project Under']
        
        updated_name = st.text_input("Part Name:", value=str(active_df.at[row_idx, 'Part Name']))
        
        col_a1, col_a2, col_a3 = st.columns(3)
        updated_project = col_a1.text_input("Project Under:", value=str(active_df.at[row_idx, 'Project Under']))
        updated_po = col_a2.text_input("PO Number Ordered Under:", value=str(active_df.at[row_idx, 'PO Number']) if pd.notna(active_df.at[row_idx, 'PO Number']) else "")
        
        current_type = str(active_df.at[row_idx, 'Part Type']) if pd.notna(active_df.at[row_idx, 'Part Type']) else ""
        known_types = sorted([t for t in active_df['Part Type'].dropna().astype(str).unique() if t.strip()])
        
        if current_type and current_type not in known_types:
            known_types.append(current_type)
        
        type_options = known_types + ["+ Add New Part Type"]
        
        default_index = type_options.index(current_type) if current_type in type_options else 0
        selected_type_opt = col_a3.selectbox("Part Type", options=type_options, index=default_index, key="alter_part_type_select")
        
        if selected_type_opt == "+ Add New Part Type":
            updated_type = col_a3.text_input("Enter New Part Type Name:", key="alter_part_type_custom").strip()
        else:
            updated_type = selected_type_opt
        
        if st.button("Save Altered Attributes"):
            if not updated_type:
                st.error("Part Type is required.")
            else:
                st.session_state["pending_action"] = {
                    "type": "alter",
                    "target_id": target_id,
                    "orig_pnum": orig_pnum,
                    "orig_loc": orig_loc,
                    "orig_proj": orig_proj,
                    "new_name": updated_name,
                    "new_proj": updated_project,
                    "new_po": updated_po,
                    "new_type": updated_type
                }
                st.rerun()

# --- TAB 7: CHANGE LOCATION ---
with tab7:
    st.header("Move Parts to a New Location")
    loc_query = st.text_input("Type any part number, name, or character fragment to change its LOCATION:", key="loc_input").strip()
    
    if loc_query:
        results = fuzzy_search_df(active_df, loc_query)
        
        if results.empty:
            st.error("No parts found matching your query.")
        else:
            options = [f"{row['Part Name']} (#{row['Part Number']}) | Proj: {row['Project Under']} | Current Loc: {row['Location']} (ID: {row.get('id', 'N/A')})" for idx, row in results.iterrows()]
            choice = st.selectbox("Select the item listing you want to move:", options, key="loc_select")
            row_idx = results.index[options.index(choice)]
            
            new_location = st.text_input("Enter new location code (Downstairs: A1-F3, Upstairs: G1-I3):")
            if st.button("Update Location"):
                valid, formatted_loc = is_valid_location(new_location)
                if not valid:
                    st.error("Invalid Location! Allowed Downstairs: A1-A3, B1-B3, C1-C4, D1-D4, E1-E4, F1-F3 | Allowed Upstairs: G1-G3, H1-H3, I1-I3")
                else:
                    target_id = active_df.at[row_idx, 'id'] if 'id' in active_df.columns else None
                    old_loc = active_df.at[row_idx, 'Location']
                    part_num = active_df.at[row_idx, 'Part Number']
                    part_name = active_df.at[row_idx, 'Part Name']
                    proj_name = active_df.at[row_idx, 'Project Under']
                    p_type = active_df.at[row_idx, 'Part Type']
                    
                    query = supabase.table("Inventory").update({"Location": formatted_loc})
                    if target_id is not None and pd.notna(target_id):
                        query = query.eq("id", target_id)
                    else:
                        query = query.eq("Part Number", str(part_num)).eq("Location", str(old_loc)).eq("Project Under", str(proj_name))
                    query.execute()
                    
                    log_event("Moved", part_num, part_name, f"Moved from {old_loc} to {formatted_loc}", project_under=proj_name, part_type=p_type)
                    st.success(f"Location updated to [{formatted_loc}] ({get_location_category(formatted_loc)})!")
                    st.rerun()

# --- TAB 8: LOG HISTORY WITH FILTERS ---
with tab8:
    st.header("Activity Log History")
    log_df = load_logs()
    if log_df.empty:
        st.info("No activity logged yet.")
    else:
        col_l1, col_l2, col_l3 = st.columns(3)
        
        action_filter = col_l1.selectbox("Filter by Action:", ["All", "Added", "Removed", "Moved", "Altered", "Disregarded"])
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

# --- SIDEBAR: LIVE INVENTORY GRID VIEW ---
st.sidebar.header("Live Inventory Grid View")
styled_df = active_df.style.apply(highlight_shortages, axis=1)
st.sidebar.dataframe(styled_df, use_container_width=True)

# --- SIDEBAR: LOW / OUT OF STOCK TABLE & DISREGARD ACTION ---
st.sidebar.markdown("---")
st.sidebar.header("⚠️ Low / Out of Stock Items")

low_stock_mask = (active_df['Qty on Hand'] <= active_df['Min Qty']) | (active_df['Qty on Hand'] == 0)
low_stock_df = active_df[low_stock_mask].copy()

if low_stock_df.empty:
    st.sidebar.success("No active low/out-of-stock items needing restock.")
else:
    display_df = low_stock_df[['Part Name', 'Part Number', 'Project Under', 'PO Number', 'Location']].copy()
    if 'id' in low_stock_df.columns:
        display_df['id'] = low_stock_df['id']
    display_df.insert(0, "Disregard", False)
    
    copy_text_lines = ["Product Name\tPart Number\tProject Under\tPO Number\tLocation"]
    for _, r in display_df.iterrows():
        copy_text_lines.append(f"{r['Part Name']}\t{r['Part Number']}\t{r['Project Under']}\t{r['PO Number']}\t{r['Location']}")
    raw_copy_str = "\\n".join(copy_text_lines).replace("'", "\\'")
    
    with st.sidebar:
        components.html(
            f"""
            <script>
            function copyTextToClipboard() {{
                const text = `{raw_copy_str}`;
                navigator.clipboard.writeText(text.replace(/\\\\n/g, '\\n')).then(function() {{
                    alert('Copied low-stock table to clipboard! Ready to paste into email.');
                }}, function(err) {{
                    console.error('Copy failed: ', err);
                }});
            }}
            </script>
            <button onclick="copyTextToClipboard()" style="
                width: 100%;
                background-color: #ff4b4b;
                color: white;
                padding: 8px 12px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-weight: bold;
                font-size: 0.85em;
                margin-bottom: 8px;">
                📋 Copy Out-of-Stock List
            </button>
            """,
            height=45
        )
    
    edited_df = st.sidebar.data_editor(
        display_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Disregard": st.column_config.CheckboxColumn(
                "Disregard",
                help="Check to remove item permanently from active list",
                default=False
            ),
            "Part Name": st.column_config.TextColumn("Product Name", disabled=True),
            "Part Number": st.column_config.TextColumn("Part Number", disabled=True),
            "Project Under": st.column_config.TextColumn("Project Under", disabled=True),
            "PO Number": st.column_config.TextColumn("PO#", disabled=True),
            "Location": st.column_config.TextColumn("Loc", disabled=True),
            "id": None
        },
        key="low_stock_editor"
    )
    
    disregarded_rows = edited_df[edited_df['Disregard'] == True]
    if not disregarded_rows.empty:
        if st.sidebar.button("Confirm Disregard Selected"):
            st.session_state["pending_action"] = {
                "type": "disregard",
                "rows": disregarded_rows
            }
            st.rerun()

# --- Sidebar Footer ---
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
