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

# --- PAGE SETUP ---
st.set_page_config(
    page_title="Panel Shop Inventory System", 
    page_icon="BlackMcDonald_Logo.webp", 
    layout="wide"
)

# Clean, lightweight CSS for scrollbars
st.markdown("""
    <style>
    /* Always visible scrollbars across main page and sidebar */
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
    </style>
""", unsafe_allow_html=True)

# Helper to normalize PO Number values
def format_po_number(val):
    if pd.isna(val) or not str(val).strip() or str(val).strip().lower() in ['none', 'nan', '']:
        return "N/A"
    return str(val).strip()

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
            df['PO Number'] = "N/A"
        else:
            df['PO Number'] = df['PO Number'].apply(format_po_number)
        return df
    except Exception as e:
        st.error(f"Error loading inventory: {e}")
        return pd.DataFrame(columns=['id', 'Part Number', 'Part Name', 'Part Type', 'Qty on Hand', 'Location', 'Project Under', 'Min Qty', 'PO Number'])

def load_locations():
    default_locations = {
        'A1': 'Downstairs', 'A2': 'Downstairs', 'A3': 'Downstairs',
        'B1': 'Downstairs', 'B2': 'Downstairs', 'B3': 'Downstairs',
        'C1': 'Downstairs', 'C2': 'Downstairs', 'C3': 'Downstairs', 'C4': 'Downstairs',
        'D1': 'Downstairs', 'D2': 'Downstairs', 'D3': 'Downstairs', 'D4': 'Downstairs',
        'E1': 'Downstairs', 'E2': 'Downstairs', 'E3': 'Downstairs', 'E4': 'Downstairs',
        'F1': 'Downstairs', 'F2': 'Downstairs', 'F3': 'Downstairs',
        'G1': 'Upstairs', 'G2': 'Upstairs', 'G3': 'Upstairs',
        'H1': 'Upstairs', 'H2': 'Upstairs', 'H3': 'Upstairs',
        'I1': 'Upstairs', 'I2': 'Upstairs', 'I3': 'Upstairs'
    }
    try:
        response = supabase.table("Locations").select("*").execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            loc_dict = dict(zip(df['Code'].str.upper(), df['Category']))
            default_locations.update(loc_dict)
    except Exception:
        pass
    return default_locations

def register_new_storage_area(letter, shelves, category):
    clean_letter = letter.strip().upper()
    registered_codes = []
    try:
        for s in range(1, int(shelves) + 1):
            code = f"{clean_letter}{s}"
            supabase.table("Locations").upsert({
                "Code": code,
                "Category": category
            }).execute()
            registered_codes.append(code)
        return True, registered_codes
    except Exception as e:
        return False, str(e)

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
        for col in ['Project Under', 'Part Type']:
            if col not in df.columns:
                df[col] = ""
        if 'PO Number' not in df.columns:
            df['PO Number'] = "N/A"
        else:
            df['PO Number'] = df['PO Number'].apply(format_po_number)
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

def is_valid_location(loc_string, location_dict):
    clean_loc = loc_string.strip().upper()
    # Accept if present in location table/dict or matches format Pattern (Letter + Number)
    if clean_loc in location_dict:
        return True, clean_loc
    if re.match(r"^[A-Z][0-9]{1,2}$", clean_loc):
        return True, clean_loc
    return False, clean_loc

def get_location_category(loc_string, location_dict):
    clean_loc = loc_string.strip().upper()
    if clean_loc in location_dict:
        return location_dict[clean_loc]
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
            st.write(f"- **PO Number:** {po}")
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
        new_pnum = action_data["new_pnum"]
        new_name, new_proj = action_data["new_name"], action_data["new_proj"]
        new_po, new_type = action_data["new_po"], action_data["new_type"]
        target_id = action_data.get("target_id")

        st.write(f"Are you sure you want to update attributes for **{new_name}**?")
        st.write(f"- **Part Number:** `{orig_pnum}` → `{new_pnum}`")
        st.write(f"- **Project Under:** {new_proj}")
        st.write(f"- **PO Number:** {new_po}")
        st.write(f"- **Part Type:** {new_type}")

        col1, col2 = st.columns(2)
        if col1.button("Yes, Save Changes", type="primary"):
            query = supabase.table("Inventory").update({
                "Part Number": str(new_pnum),
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
            
            log_event("Altered", new_pnum, new_name, f"Updated Attributes (Orig P/N: {orig_pnum}, PO#: {new_po}).", project_under=new_proj, part_type=new_type)
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
            st.write(f"- **{r['Part Name']}** (`{r['Part Number']}`) [Project: {r['Project Under']}]")

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
location_dict = load_locations()
active_df = df.copy()

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "Scan Search", 
    "Location Search",
    "Project & PO Search",
    "Add Inventory", 
    "Take Inventory", 
    "Alter Part",
    "Change Part Location",
    "Log History",
    "Full Inventory Table"
])

# --- TAB 1: SCAN SEARCH ---
with tab1:
    st.header("Search Database by Part")
    
    components.html("""
        <script>
        const doc = window.parent.document;
        doc.addEventListener('DOMContentLoaded', () => {
            const scanInput = doc.querySelector('input[aria-label*="Click here to SCAN"]');
            if (scanInput) {
                scanInput.addEventListener('focus', () => scanInput.select());
                scanInput.addEventListener('click', () => scanInput.select());
            }
        });
        </script>
    """, height=0, width=0)
    
    search_query = st.text_input(
        "Click here to SCAN a barcode, or TYPE part details (Name, Number, Type, PO#):", 
        key="search_input"
    ).strip()
    
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
                        loc_cat = get_location_category(str(row['Location']), location_dict)
                        st.caption("Location")
                        st.markdown(f"### [{row['Location']}] *({loc_cat})*")
                    with col6:
                        st.caption("Project / PO#")
                        st.markdown(f"**Proj:** {row['Project Under']}\n\n**PO#:** {format_po_number(row.get('PO Number'))}")
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

# --- TAB 2: LOCATION SEARCH & NEW LOCATION CREATOR ---
with tab2:
    st.header("Search Database by Storage Location")
    
    col_l1, col_l2 = st.columns(2)
    selected_floor = col_l1.selectbox("Filter by Floor Category:", ["All Floors", "Downstairs", "Upstairs"], key="floor_select")
    loc_search_query = col_l2.text_input("Or TYPE Specific Location Code (e.g. C3, G1, J2):", key="loc_search_input").strip().upper()
    
    results = active_df.copy()
    
    if selected_floor == "Downstairs":
        downstairs_codes = [code for code, cat in location_dict.items() if cat == "Downstairs"]
        results = results[results['Location'].astype(str).str.upper().isin(downstairs_codes) | results['Location'].astype(str).str.upper().str.match(r"^[A-F]")]
    elif selected_floor == "Upstairs":
        upstairs_codes = [code for code, cat in location_dict.items() if cat == "Upstairs"]
        results = results[results['Location'].astype(str).str.upper().isin(upstairs_codes) | results['Location'].astype(str).str.upper().str.match(r"^[G-I]")]
        
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
                    loc_cat = get_location_category(str(row['Location']), location_dict)
                    st.caption("Location")
                    st.markdown(f"### [{row['Location']}] *({loc_cat})*")
                with col6:
                    st.caption("Project / PO#")
                    st.markdown(f"**Proj:** {row['Project Under']}\n\n**PO#:** {format_po_number(row.get('PO Number'))}")
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

    # --- DYNAMIC STORAGE ADDITION FORM ---
    st.markdown("---")
    with st.expander("➕ Add / Register New Storage Area (Letters & Shelves)", expanded=False):
        st.write("Register a new storage section to expand shop capacity:")
        
        col_new_l1, col_new_l2, col_new_l3 = st.columns(3)
        new_letter = col_new_l1.text_input("Section Alphabetical Letter (e.g. J, K, L):", max_chars=2).strip().upper()
        new_shelves = col_new_l2.number_input("Number of Shelves/Sections (e.g. 4 creates J1-J4):", min_value=1, max_value=20, value=3)
        new_floor_cat = col_new_l3.selectbox("Storage Area Level:", ["Downstairs", "Upstairs"])
        
        if st.button("Register Storage Section"):
            if not new_letter or not new_letter.isalpha():
                st.error("Please enter a valid alphabetical letter for the section.")
            else:
                success, created_codes = register_new_storage_area(new_letter, new_shelves, new_floor_cat)
                if success:
                    st.success(f"Successfully registered storage locations: {', '.join(created_codes)} ({new_floor_cat})!")
                    log_event("Added Location", f"{new_letter}1-{new_letter}{new_shelves}", "New Storage Section", f"Created {new_shelves} shelves at {new_floor_cat}")
                    st.rerun()
                else:
                    st.error(f"Error registering storage section: {created_codes}")

# --- TAB 3: PROJECT & PO SEARCH ---
with tab3:
    st.header("Search Database by Project Under or PO Number")
    
    col_p1, col_p2 = st.columns(2)
    col_po1, col_po2 = st.columns(2)
    
    known_projects = ["Select a Project..."] + sorted([p for p in active_df['Project Under'].dropna().astype(str).unique() if p.strip()])
    selected_proj_dropdown = col_p1.selectbox("Select from existing projects:", known_projects, key="proj_search_select")
    proj_search_query = col_p2.text_input("Or TYPE a project name:", key="proj_search_input").strip()
    
    known_pos = ["Select a PO Number..."] + sorted([po for po in active_df['PO Number'].dropna().astype(str).unique() if po.strip() and po != 'N/A'])
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
                        loc_cat = get_location_category(str(row['Location']), location_dict)
                        st.caption("Location")
                        st.markdown(f"### [{row['Location']}] *({loc_cat})*")
                    with col6:
                        st.caption("Project / PO#")
                        st.markdown(f"**Proj:** {row['Project Under']}\n\n**PO#:** {format_po_number(row.get('PO Number'))}")
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
        new_loc = st.text_input("Storage Location (e.g., A1-F3 downstairs, G1-I3 upstairs, or registered area):")
        
        col_n1, col_n2 = st.columns(2)
        new_proj = col_n1.text_input("Project Under:")
        new_po = col_n2.text_input("PO Number Ordered Under (Optional, defaults to N/A):")
        
        new_min_qty = st.number_input("Minimum Quantity Alert Threshold (Optional, set 0 for None):", min_value=0, step=10, value=0)
        
        if st.button("Save Brand New Item"):
            valid, formatted_loc = is_valid_location(new_loc, location_dict)
            final_po = format_po_number(new_po)
            
            if not new_num.strip():
                st.error("Part Number is required.")
            elif not new_type:
                st.error("Part Type is required.")
            elif not valid:
                st.error(f"Invalid Location '{new_loc}'! Location must be in format Letter+Number (e.g. C4, J2). You can register custom sections in Tab 2.")
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
                    "po": final_po,
                    "min_qty": new_min_qty
                }
                st.rerun()

    elif not results.empty:
        if add_query:
            st.success(f"Found {len(results)} matching item(s):")
        options = [f"{row['Part Name']} (#{row['Part Number']}) | Type: {row['Part Type']} | Proj: {row['Project Under']} | PO#: {format_po_number(row['PO Number'])} | Qty: {row['Qty on Hand']} | Loc: {row['Location']} (ID: {row.get('id', 'N/A')})" for idx, row in results.iterrows()]
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
            target_po = format_po_number(active_df.at[row_idx, 'PO Number'])
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
        options = [f"{row['Part Name']} (#{row['Part Number']}) | Type: {row['Part Type']} | Proj: {row['Project Under']} | PO#: {format_po_number(row['PO Number'])} | Qty: {row['Qty on Hand']} | Loc: {row['Location']} (ID: {row.get('id', 'N/A')})" for idx, row in results.iterrows()]
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
        options = [f"{row['Part Name']} (#{row['Part Number']}) | Proj: {row['Project Under']} | PO#: {format_po_number(row['PO Number'])} | Loc: {row['Location']} (ID: {row.get('id', 'N/A')})" for idx, row in results.iterrows()]
        choice = st.selectbox("Select the exact item to edit:", options, key="alter_select")
        row_idx = results.index[options.index(choice)]
        
        st.subheader(f"Editing Part: {active_df.at[row_idx, 'Part Number']}")
        
        target_id = active_df.at[row_idx, 'id'] if 'id' in active_df.columns else None
        orig_pnum = active_df.at[row_idx, 'Part Number']
        orig_loc = active_df.at[row_idx, 'Location']
        orig_proj = active_df.at[row_idx, 'Project Under']
        
        col_edit1, col_edit2 = st.columns(2)
        updated_pnum = col_edit1.text_input("Part Number:", value=str(orig_pnum))
        updated_name = col_edit2.text_input("Part Name:", value=str(active_df.at[row_idx, 'Part Name']))
        
        col_a1, col_a2, col_a3 = st.columns(3)
        updated_project = col_a1.text_input("Project Under:", value=str(active_df.at[row_idx, 'Project Under']))
        
        existing_po_raw = active_df.at[row_idx, 'PO Number']
        updated_po = col_a2.text_input("PO Number Ordered Under (Optional):", value="" if existing_po_raw == "N/A" else str(existing_po_raw))
        
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
            final_po = format_po_number(updated_po)
            if not updated_pnum.strip():
                st.error("Part Number is required.")
            elif not updated_type:
                st.error("Part Type is required.")
            else:
                st.session_state["pending_action"] = {
                    "type": "alter",
                    "target_id": target_id,
                    "orig_pnum": orig_pnum,
                    "new_pnum": updated_pnum.strip(),
                    "orig_loc": orig_loc,
                    "orig_proj": orig_proj,
                    "new_name": updated_name,
                    "new_proj": updated_project,
                    "new_po": final_po,
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
            
            new_location = st.text_input("Enter new location code (e.g. A1, G3, J2):")
            if st.button("Update Location"):
                valid, formatted_loc = is_valid_location(new_location, location_dict)
                if not valid:
                    st.error(f"Invalid Location '{new_location}'! Format must be Letter+Number (e.g. C3, J1). Register new sections in Tab 2.")
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
                    st.success(f"Location updated to [{formatted_loc}] ({get_location_category(formatted_loc, location_dict)})!")
                    st.rerun()

# --- TAB 8: LOG HISTORY WITH CALENDAR DATE SEARCH ---
with tab8:
    st.header("Activity Log History")
    log_df = load_logs()
    
    if log_df.empty:
        st.info("No activity logged yet.")
    else:
        log_df['Timestamp_DT'] = pd.to_datetime(log_df['Timestamp'], errors='coerce')
        valid_dates = log_df['Timestamp_DT'].dropna()
        
        min_date = valid_dates.min().date() if not valid_dates.empty else pd.Timestamp.today().date()
        today_date = pd.Timestamp.today().date()
        
        st.subheader("Filter Logs by Calendar Date")
        col_cal1, col_cal2 = st.columns([1.5, 2.5])
        
        selected_date = col_cal1.date_input(
            "Select a specific date to view historical activity:",
            value=None,
            min_value=min_date,
            max_value=today_date,
            key="log_calendar_picker"
        )
        
        if col_cal2.button("Clear Date Filter / Show All History"):
            st.rerun()

        col_l1, col_l2, col_l3 = st.columns(3)
        action_filter = col_l1.selectbox("Filter by Action:", ["All", "Added", "Removed", "Moved", "Altered", "Disregarded", "Added Location"])
        log_proj_filter = col_l2.selectbox("Filter by Project Under:", ["All Projects"] + sorted(list(set(log_df['Project Under'].dropna().astype(str).unique()))))
        log_type_filter = col_l3.selectbox("Filter by Part Type:", ["All Part Types"] + sorted([t for t in log_df['Part Type'].dropna().astype(str).unique() if t.strip()]))
        
        filtered_logs = log_df.copy()
        
        if selected_date is not None:
            filtered_logs = filtered_logs[filtered_logs['Timestamp_DT'].dt.date == selected_date]
            st.caption(f"Showing **{len(filtered_logs)}** log event(s) recorded on **{selected_date.strftime('%B %d, %Y')}**:")
            
        if action_filter != "All":
            filtered_logs = filtered_logs[filtered_logs['Action'] == action_filter]
        if log_proj_filter != "All Projects":
            filtered_logs = filtered_logs[filtered_logs['Project Under'] == log_proj_filter]
        if log_type_filter != "All Part Types":
            filtered_logs = filtered_logs[filtered_logs['Part Type'] == log_type_filter]
            
        display_logs = filtered_logs.drop(columns=['Timestamp_DT'], errors='ignore')
        st.dataframe(display_logs.iloc[::-1], use_container_width=True)

# --- TAB 9: FULL INVENTORY TABLE ---
with tab9:
    st.header("Full Live Inventory Grid View")
    st.caption("Hover over the table top-right corner to search, sort columns, or click Fullscreen.")
    
    main_display_df = active_df.drop(columns=['id'], errors='ignore')
    st.dataframe(main_display_df, use_container_width=True)

# --- SIDEBAR: LIVE INVENTORY GRID VIEW ---
st.sidebar.header("Live Inventory Grid View")

display_sidebar_df = active_df.drop(columns=['id'], errors='ignore')
st.sidebar.dataframe(display_sidebar_df, use_container_width=True)

# --- SIDEBAR: LOW / OUT OF STOCK TABLE (WITH EDITABLE PO AND ORDER QTY) ---
st.sidebar.markdown("---")
st.sidebar.header("⚠️ Low / Out of Stock Items")

low_stock_mask = (active_df['Qty on Hand'] <= active_df['Min Qty']) | (active_df['Qty on Hand'] == 0)
low_stock_df = active_df[low_stock_mask].copy()

if low_stock_df.empty:
    st.sidebar.success("No active low/out-of-stock items needing restock.")
else:
    # Reordered columns: Part Name, Part Number, Qty on Hand, PO Number, Project Under
    display_df = low_stock_df[['Part Name', 'Part Number', 'Qty on Hand', 'PO Number', 'Project Under']].copy()
    display_df['PO Number'] = display_df['PO Number'].apply(format_po_number)
    
    if 'id' in low_stock_df.columns:
        row_ids = low_stock_df['id'].tolist()
    else:
        row_ids = [None] * len(low_stock_df)
        
    display_df.insert(0, "Disregard", False)
    display_df['Order Qty'] = 0
    
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
            "Part Name": st.column_config.TextColumn("Part Name", disabled=True),
            "Part Number": st.column_config.TextColumn("Part Number", disabled=True),
            "Qty on Hand": st.column_config.NumberColumn("Current Qty", disabled=True),
            "PO Number": st.column_config.TextColumn("PO Under", help="Click to edit PO#; leaving blank sets to N/A"),
            "Project Under": st.column_config.TextColumn("Project Under", disabled=True),
            "Order Qty": st.column_config.NumberColumn("Order Qty", min_value=0, step=1, help="Type quantity needed for purchase email")
        },
        key="low_stock_editor"
    )
    
    # Check for direct PO edits in data editor and update Supabase seamlessly
    for idx, r in edited_df.iterrows():
        current_entered_po = format_po_number(r['PO Number'])
        original_po = display_df.loc[idx, 'PO Number']
        if current_entered_po != original_po:
            target_id = row_ids[idx]
            p_num = r['Part Number']
            p_proj = r['Project Under']
            
            query = supabase.table("Inventory").update({"PO Number": current_entered_po})
            if target_id is not None and pd.notna(target_id):
                query = query.eq("id", target_id)
            else:
                query = query.eq("Part Number", str(p_num)).eq("Project Under", str(p_proj))
            query.execute()
            log_event("Altered", p_num, r['Part Name'], f"Updated PO# from {original_po} to {current_entered_po}", project_under=p_proj)
            st.rerun()

    # Generate Clipboard Text including typed Order Qty
    copy_text_lines = ["Part Name\tPart Number\tCurrent Qty\tPO Under\tProject Under\tOrder Qty"]
    for _, r in edited_df.iterrows():
        order_val = int(r['Order Qty']) if pd.notna(r['Order Qty']) and r['Order Qty'] > 0 else ""
        po_val = format_po_number(r['PO Number'])
        copy_text_lines.append(f"{r['Part Name']}\t{r['Part Number']}\t{int(r['Qty on Hand'])}\t{po_val}\t{r['Project Under']}\t{order_val}")
    raw_copy_str = "\\n".join(copy_text_lines).replace("'", "\\'")
    
    with st.sidebar:
        components.html(
            f"""
            <script>
            function copyTextToClipboard() {{
                const text = `{raw_copy_str}`;
                navigator.clipboard.writeText(text.replace(/\\\\n/g, '\\n')).then(function() {{
                    alert('Copied low-stock table with order quantities to clipboard! Ready to paste into email.');
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
    
    disregarded_indices = edited_df[edited_df['Disregard'] == True].index.tolist()
    if disregarded_indices:
        disregarded_rows_to_process = []
        for idx in disregarded_indices:
            row_data = edited_df.loc[idx].to_dict()
            row_data['id'] = row_ids[idx] if idx < len(row_ids) else None
            disregarded_rows_to_process.append(row_data)
            
        disregarded_df_to_process = pd.DataFrame(disregarded_rows_to_process)
        
        if st.sidebar.button("Confirm Disregard Selected"):
            st.session_state["pending_action"] = {
                "type": "disregard",
                "rows": disregarded_df_to_process
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
