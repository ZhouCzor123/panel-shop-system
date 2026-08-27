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

def format_na_str(val):
    if pd.isna(val) or not str(val).strip() or str(val).strip().lower() in ['none', 'nan', '']:
        return "N/A"
    return str(val).strip()

# --- DATABASE LOADERS ---
def load_permanent_data():
    try:
        response = supabase.table("Inventory").select("*").execute()
        df = pd.DataFrame(response.data)
        if df.empty:
            return pd.DataFrame(columns=['id', 'Part Name', 'Part Number', 'Manufacturer', 'Qty on Hand', 'Location', 'Project Under', 'PO Number', 'Min Qty', 'Part Type'])
        
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
            df['PO Number'] = df['PO Number'].apply(format_na_str)
        if 'Manufacturer' not in df.columns:
            df['Manufacturer'] = "N/A"
        else:
            df['Manufacturer'] = df['Manufacturer'].apply(format_na_str)
        return df
    except Exception as e:
        st.error(f"Error loading inventory: {e}")
        return pd.DataFrame(columns=['id', 'Part Name', 'Part Number', 'Manufacturer', 'Qty on Hand', 'Location', 'Project Under', 'PO Number', 'Min Qty', 'Part Type'])

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

def alter_storage_area(letter, new_shelves, new_category, location_dict):
    clean_letter = letter.strip().upper()
    try:
        existing_in_letter = [code for code in location_dict.keys() if re.match(rf"^{clean_letter}[0-9]+$", code)]
        for code in existing_in_letter:
            supabase.table("Locations").delete().eq("Code", code).execute()
        
        registered_codes = []
        for s in range(1, int(new_shelves) + 1):
            code = f"{clean_letter}{s}"
            supabase.table("Locations").upsert({
                "Code": code,
                "Category": new_category
            }).execute()
            registered_codes.append(code)
        return True, registered_codes
    except Exception as e:
        return False, str(e)

def delete_storage_area(letter, location_dict):
    clean_letter = letter.strip().upper()
    try:
        existing_in_letter = [code for code in location_dict.keys() if re.match(rf"^{clean_letter}[0-9]+$", code)]
        for code in existing_in_letter:
            supabase.table("Locations").delete().eq("Code", code).execute()
        return True, existing_in_letter
    except Exception as e:
        return False, str(e)

def delete_inventory_row(row_id, part_num, project_under, location):
    try:
        if row_id is not None and pd.notna(row_id):
            supabase.table("Inventory").delete().eq("id", row_id).execute()
        else:
            supabase.table("Inventory").delete().eq("Part Number", str(part_num)).eq("Project Under", str(project_under)).eq("Location", str(location)).execute()
            
        try:
            supabase.table("Disregarded_Items").insert({
                "Part Number": str(part_num),
                "Project Under": str(project_under),
                "Location": str(location)
            }).execute()
        except Exception:
            try:
                supabase.table("Disregarded_Items").insert({
                    "Part Number": str(part_num),
                    "Project Under": str(project_under)
                }).execute()
            except Exception:
                pass
                
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error removing item: {e}")

def load_logs():
    try:
        response = supabase.table("Logs").select("*").execute()
        df = pd.DataFrame(response.data)
        if df.empty:
            return pd.DataFrame(columns=['Timestamp', 'Action', 'Part Number', 'Part Name', 'Manufacturer', 'Project Under', 'Part Type', 'Details'])
        
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
            df['PO Number'] = df['PO Number'].apply(format_na_str)
        if 'Manufacturer' not in df.columns:
            df['Manufacturer'] = "N/A"
        else:
            df['Manufacturer'] = df['Manufacturer'].apply(format_na_str)
        return df
    except Exception:
        return pd.DataFrame(columns=['Timestamp', 'Action', 'Part Number', 'Part Name', 'Manufacturer', 'Project Under', 'Part Type', 'Details'])

def log_event(action, part_num, part_name, details, project_under="", part_type="", manufacturer="N/A"):
    try:
        eastern_tz = pytz.timezone('America/Toronto')
        current_time = pd.Timestamp.now(tz=eastern_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        supabase.table("Logs").insert({
            'Timestamp': current_time,
            'Action': str(action),
            'Part Number': str(part_num),
            'Part Name': str(part_name),
            'Manufacturer': str(manufacturer),
            'Project Under': str(project_under),
            'Part Type': str(part_type),
            'Details': str(details)
        }).execute()
    except Exception as e:
        st.error(f"Error logging event: {e}")

def is_valid_location(loc_string, location_dict):
    clean_loc = loc_string.strip().upper()
    if clean_loc in location_dict:
        return True, clean_loc
    return False, clean_loc

def get_location_category(loc_string, location_dict):
    clean_loc = loc_string.strip().upper()
    if clean_loc in location_dict:
        return location_dict[clean_loc]
    return "Unregistered"

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
        dataframe['Manufacturer'].apply(normalize_str).str.contains(norm_query, na=False) |
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
if "show_new_part_form" not in st.session_state:
    st.session_state["show_new_part_form"] = False

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
        mfg = action_data.get("mfg", "N/A")
        current_qty = action_data.get("current_qty", 0)
        target_id = action_data.get("target_id")
        initial_is_corr = action_data.get("is_correction", False)

        if is_new:
            st.write(f"Registering separate stock entry for **{pname}** (`{pnum}`):")
            st.write(f"- **Manufacturer:** {mfg}")
            st.write(f"- **Initial Quantity:** {amt}")
            st.write(f"- **Target Location:** {loc}")
            st.write(f"- **Target Project:** {proj}")
            st.write(f"- **PO Number:** {po}")
            is_corr_dialog = False
        else:
            is_corr_dialog = st.checkbox("System Inventory Count Correction (Not a physical delivery/consumption)", value=initial_is_corr)
            st.write(f"Adding **{amt}** units to **{pname}** (`{pnum}`):")
            st.write(f"- **Current Stock on Hand:** {current_qty}")
            st.write(f"- **New Total Quantity:** {current_qty + amt}")
            st.write(f"- **Location:** {loc}")
            st.write(f"- **Project:** {proj}")

        col1, col2 = st.columns(2)
        if col1.button("Yes, Confirm Add", type="primary"):
            log_action_name = "Corrected (+)" if is_corr_dialog else "Added"
            
            if is_new:
                supabase.table("Inventory").insert({
                    "Part Number": str(pnum),
                    "Part Name": str(pname),
                    "Manufacturer": str(mfg),
                    "Part Type": str(ptype),
                    "Qty on Hand": int(amt),
                    "Location": str(loc),
                    "Project Under": str(proj),
                    "PO Number": str(po),
                    "Min Qty": int(min_qty)
                }).execute()
                log_event("Added", pnum, pname, f"Registered new stock entry. Initial Qty {amt} at {loc}. Proj: {proj}, PO#: {po}", project_under=proj, part_type=ptype, manufacturer=mfg)
            else:
                query = supabase.table("Inventory").update({
                    "Qty on Hand": current_qty + amt,
                    "Min Qty": int(min_qty)
                })
                if target_id is not None and pd.notna(target_id):
                    query = query.eq("id", target_id)
                else:
                    query = query.eq("Part Number", str(pnum)).eq("Location", str(loc)).eq("Project Under", str(proj))
                query.execute()
                log_event(log_action_name, pnum, pname, f"{'Correction' if is_corr_dialog else 'Added'}: Adjusted +{amt} units at [{loc}] under '{proj}'. New Total: {current_qty + amt}.", project_under=proj, part_type=ptype, manufacturer=mfg)
            
            st.session_state["pending_action"] = None
            st.session_state["show_new_part_form"] = False
            st.success("Stock updated permanently!")
            st.rerun()

        if col2.button("No, Cancel"):
            st.session_state["pending_action"] = None
            st.rerun()

    elif action_type == "take":
        pnum, pname = action_data["pnum"], action_data["pname"]
        amt, loc, proj = action_data["amt"], action_data["loc"], action_data["proj"]
        ptype, current_qty, min_qty = action_data["ptype"], action_data["current_qty"], action_data["min_qty"]
        mfg = action_data.get("mfg", "N/A")
        target_id = action_data.get("target_id")
        initial_is_corr = action_data.get("is_correction", False)
        
        actual_deducted = min(current_qty, amt)
        new_stock = max(0, current_qty - amt)

        is_corr_dialog = st.checkbox("System Inventory Count Correction (Not a physical assembly/usage)", value=initial_is_corr)

        st.write(f"Removing units of **{pname}** (`{pnum}`):")
        st.write(f"- **Current Stock on Hand:** {current_qty}")
        if amt > current_qty:
            st.warning(f"⚠️ Requested removal of **{amt}** units exceeds available stock. Only the remaining **{actual_deducted}** units will be deducted.")
        else:
            st.write(f"- **Quantity Deducted:** {actual_deducted}")
        st.write(f"- **Remaining Stock After Removal:** {new_stock}")

        col1, col2 = st.columns(2)
        if col1.button("Yes, Confirm Removal", type="primary"):
            log_action_name = "Corrected (-)" if is_corr_dialog else "Removed"
            query = supabase.table("Inventory").update({"Qty on Hand": new_stock})
            if target_id is not None and pd.notna(target_id):
                query = query.eq("id", target_id)
            else:
                query = query.eq("Part Number", str(pnum)).eq("Location", str(loc)).eq("Project Under", str(proj))
            query.execute()

            if new_stock <= 0:
                log_event(log_action_name, pnum, pname, f"{'Correction' if is_corr_dialog else 'Removed'}: Adjusted -{actual_deducted} units. Stock hit 0.", project_under=proj, part_type=ptype, manufacturer=mfg)
                st.toast(f"🚨 ALERT: {pname} has hit 0 and is completely out of stock!", icon="🚨")
            else:
                log_event(log_action_name, pnum, pname, f"{'Correction' if is_corr_dialog else 'Removed'}: Adjusted -{actual_deducted} units. Remaining: {new_stock}", project_under=proj, part_type=ptype, manufacturer=mfg)
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
        new_mfg = action_data["new_mfg"]
        new_min_qty = action_data["new_min_qty"]
        target_id = action_data["target_id"]
        merge_target_id = action_data.get("merge_target_id")
        merge_add_qty = action_data.get("merge_add_qty", 0)
        dest_curr_qty = action_data.get("dest_curr_qty", 0)

        if merge_target_id:
            st.warning(f"⚠️ Merge Detected: Part `{new_pnum}` already exists under Project '{new_proj}'.")
            st.write(f"The **{merge_add_qty}** units from this row will be combined into Project '{new_proj}' (New Total: **{dest_curr_qty + merge_add_qty}** units), adopting PO#: **{new_po}**, and this old row will be removed.")
        else:
            st.write(f"Are you sure you want to update attributes for **{new_name}**?")
            st.write(f"- **Part Number:** `{orig_pnum}` → `{new_pnum}`")
            st.write(f"- **Manufacturer:** {new_mfg}")
            st.write(f"- **Min Qty Threshold:** {new_min_qty}")
            st.write(f"- **Project Under:** {new_proj}")
            st.write(f"- **PO Number:** {new_po}")
            st.write(f"- **Part Type:** {new_type}")

        col1, col2 = st.columns(2)
        if col1.button("Yes, Save Changes", type="primary"):
            if merge_target_id:
                supabase.table("Inventory").update({
                    "Qty on Hand": dest_curr_qty + merge_add_qty,
                    "PO Number": str(new_po),
                    "Manufacturer": str(new_mfg),
                    "Part Type": str(new_type)
                }).eq("id", merge_target_id).execute()

                supabase.table("Inventory").delete().eq("id", target_id).execute()
                log_event("Compiled / Merged", new_pnum, new_name, f"Transferred {merge_add_qty} units into Project '{new_proj}' (Total: {dest_curr_qty + merge_add_qty}). Old row deleted.", project_under=new_proj, part_type=new_type, manufacturer=new_mfg)
            else:
                query = supabase.table("Inventory").update({
                    "Part Number": str(new_pnum),
                    "Part Name": str(new_name),
                    "Manufacturer": str(new_mfg),
                    "Min Qty": int(new_min_qty),
                    "Project Under": str(new_proj),
                    "PO Number": str(new_po),
                    "Part Type": str(new_type)
                })
                if target_id is not None and pd.notna(target_id):
                    query = query.eq("id", target_id)
                else:
                    query = query.eq("Part Number", str(orig_pnum))
                query.execute()
                log_event("Altered", new_pnum, new_name, f"Updated Attributes (Orig P/N: {orig_pnum}, Mfg: {new_mfg}, PO#: {new_po}, MinQty: {new_min_qty}).", project_under=new_proj, part_type=new_type, manufacturer=new_mfg)
            
            st.session_state["pending_action"] = None
            st.success("Part attributes successfully updated!")
            st.rerun()

        if col2.button("No, Cancel"):
            st.session_state["pending_action"] = None
            st.rerun()

    elif action_type == "transfer_project_bulk":
        src_proj = action_data["src_proj"]
        dest_proj = action_data["dest_proj"]
        items_to_transfer = action_data["items"]
        
        st.write(f"Are you sure you want to transfer **{len(items_to_transfer)}** selected item row(s) from Project **'{src_proj}'** to **'{dest_proj}'**?")
        for item in items_to_transfer:
            st.write(f"- `{item['Part Number']}` ({item['Part Name']}) — Qty: {item['Qty on Hand']} at [{item['Location']}]")

        col1, col2 = st.columns(2)
        if col1.button("Yes, Confirm Bulk Transfer", type="primary"):
            for item in items_to_transfer:
                row_id = item["id"]
                pnum = item["Part Number"]
                pname = item["Part Name"]
                ploc = item["Location"]
                pqty = int(item["Qty on Hand"])
                pmfg = item["Manufacturer"]
                ptype = item["Part Type"]
                
                # Check if matching record exists in destination project at same location
                norm_pnum = normalize_str(pnum)
                norm_dest_proj = normalize_str(dest_proj)
                norm_loc = normalize_str(ploc)
                
                existing_match = active_df[
                    (active_df['Part Number'].apply(normalize_str) == norm_pnum) &
                    (active_df['Project Under'].apply(normalize_str) == norm_dest_proj) &
                    (active_df['Location'].apply(normalize_str) == norm_loc) &
                    (active_df['id'] != row_id)
                ]
                
                if not existing_match.empty:
                    dest_match_idx = existing_match.index[0]
                    dest_row_id = existing_match.at[dest_match_idx, 'id']
                    dest_curr_qty = int(existing_match.at[dest_match_idx, 'Qty on Hand'])
                    dest_po = format_na_str(existing_match.at[dest_match_idx, 'PO Number'])
                    
                    # Merge quantities into target row
                    supabase.table("Inventory").update({
                        "Qty on Hand": dest_curr_qty + pqty,
                        "PO Number": str(dest_po)
                    }).eq("id", dest_row_id).execute()
                    
                    # Delete source row
                    supabase.table("Inventory").delete().eq("id", row_id).execute()
                    log_event("Compiled / Merged", pnum, pname, f"Bulk project transfer merged {pqty} units from '{src_proj}' into '{dest_proj}' at [{ploc}] (New Total: {dest_curr_qty + pqty}).", project_under=dest_proj, part_type=ptype, manufacturer=pmfg)
                else:
                    # Update source row's project
                    supabase.table("Inventory").update({
                        "Project Under": str(dest_proj)
                    }).eq("id", row_id).execute()
                    log_event("Altered", pnum, pname, f"Bulk transferred project assignment from '{src_proj}' to '{dest_proj}' at [{ploc}].", project_under=dest_proj, part_type=ptype, manufacturer=pmfg)

            st.session_state["pending_action"] = None
            st.success(f"Successfully transferred selected items to '{dest_proj}'!")
            st.rerun()

        if col2.button("No, Cancel"):
            st.session_state["pending_action"] = None
            st.rerun()

    elif action_type == "delete_project":
        proj_to_delete = action_data["project"]
        st.write(f"Are you sure you want to completely remove Project **'{proj_to_delete}'** from system records?")

        col1, col2 = st.columns(2)
        if col1.button("Yes, Delete Project", type="primary"):
            log_event("Deleted Project", "PROJECT", proj_to_delete, f"Deleted empty project '{proj_to_delete}' from system records.", project_under=proj_to_delete)
            st.session_state["pending_action"] = None
            st.success(f"Project '{proj_to_delete}' deleted from active records!")
            st.rerun()

        if col2.button("No, Cancel"):
            st.session_state["pending_action"] = None
            st.rerun()

    elif action_type == "move_part":
        part_num = action_data["part_num"]
        part_name = action_data["part_name"]
        old_loc = action_data["old_loc"]
        new_loc = action_data["new_loc"]
        proj_name = action_data["proj_name"]
        p_type = action_data["p_type"]
        mfg = action_data.get("mfg", "N/A")
        target_id = action_data.get("target_id")

        st.write(f"Are you sure you want to move **{part_name}** (`{part_num}`)?")
        st.write(f"- **Current Location:** [{old_loc}]")
        st.write(f"- **New Location:** [{new_loc}]")

        col1, col2 = st.columns(2)
        if col1.button("Yes, Confirm Move", type="primary"):
            query = supabase.table("Inventory").update({"Location": new_loc})
            if target_id is not None and pd.notna(target_id):
                query = query.eq("id", target_id)
            else:
                query = query.eq("Part Number", str(part_num)).eq("Location", str(old_loc)).eq("Project Under", str(proj_name))
            query.execute()
            
            log_event("Moved", part_num, part_name, f"Moved from {old_loc} to {new_loc}", project_under=proj_name, part_type=p_type, manufacturer=mfg)
            st.session_state["pending_action"] = None
            st.success(f"Location updated to [{new_loc}]!")
            st.rerun()

        if col2.button("No, Cancel"):
            st.session_state["pending_action"] = None
            st.rerun()

    elif action_type == "add_location":
        letter = action_data["letter"]
        shelves = action_data["shelves"]
        category = action_data["category"]

        st.write(f"Are you sure you want to register new storage area **Section {letter}**?")
        st.write(f"- **Shelves/Codes:** {letter}1 to {letter}{shelves}")
        st.write(f"- **Level:** {category}")

        col1, col2 = st.columns(2)
        if col1.button("Yes, Register Section", type="primary"):
            success, created_codes = register_new_storage_area(letter, shelves, category)
            if success:
                log_event("Added Location", f"{letter}1-{letter}{shelves}", "New Storage Section", f"Created {shelves} shelves at {category}")
                st.session_state["pending_action"] = None
                st.success(f"Successfully registered storage locations: {', '.join(created_codes)} ({category})!")
                st.rerun()
            else:
                st.error(f"Error registering storage section: {created_codes}")

        if col2.button("No, Cancel"):
            st.session_state["pending_action"] = None
            st.rerun()

    elif action_type == "alter_location":
        letter = action_data["letter"]
        shelves = action_data["shelves"]
        category = action_data["category"]
        loc_dict = action_data["loc_dict"]

        st.write(f"Are you sure you want to alter storage configuration for **Section {letter}**?")
        st.write(f"- **New Configuration:** {letter}1 to {letter}{shelves}")
        st.write(f"- **Level Category:** {category}")

        col1, col2 = st.columns(2)
        if col1.button("Yes, Save Section Changes", type="primary"):
            success, codes = alter_storage_area(letter, shelves, category, loc_dict)
            if success:
                log_event("Altered Location", f"{letter}1-{letter}{shelves}", "Storage Section Config", f"Updated to {shelves} shelves at {category}")
                st.session_state["pending_action"] = None
                st.success(f"Successfully updated Section {letter} configuration!")
                st.rerun()
            else:
                st.error(f"Error updating section: {codes}")

        if col2.button("No, Cancel"):
            st.session_state["pending_action"] = None
            st.rerun()

    elif action_type == "delete_location":
        letter = action_data["letter"]
        loc_dict = action_data["loc_dict"]

        st.write(f"Are you sure you want to permanently delete **Section {letter}** and all its shelves?")

        col1, col2 = st.columns(2)
        if col1.button("Yes, Delete Section", type="primary"):
            success, deleted_codes = delete_storage_area(letter, loc_dict)
            if success:
                log_event("Deleted Location", f"Section {letter}", "Deleted Storage Section", f"Removed codes: {', '.join(deleted_codes)}")
                st.session_state["pending_action"] = None
                st.success(f"Successfully deleted Section {letter}!")
                st.rerun()
            else:
                st.error(f"Error deleting section: {deleted_codes}")

        if col2.button("No, Cancel"):
            st.session_state["pending_action"] = None
            st.rerun()

    elif action_type == "disregard":
        disregarded_rows = action_data["rows"]
        st.write("Are you sure you want to disregard and permanently remove the following out-of-stock item(s)?")
        for _, r in disregarded_rows.iterrows():
            st.write(f"- **{r['Part Name']}** (`{r['Part Number']}`) [Project: {r['Project Under']} | Loc: {r['Location']}]")

        col1, col2 = st.columns(2)
        if col1.button("Yes, Confirm Disregard", type="primary"):
            for _, r in disregarded_rows.iterrows():
                row_id = r.get('id') if 'id' in r and pd.notna(r['id']) else None
                delete_inventory_row(row_id, r['Part Number'], r['Project Under'], r['Location'])
                log_event("Disregarded", r['Part Number'], r['Part Name'], f"Disregarded row ID: {row_id} at {r['Location']}", project_under=r['Project Under'], manufacturer=r.get('Manufacturer', 'N/A'))
            st.session_state["pending_action"] = None
            st.success("Item(s) disregarded and deleted from inventory!")
            st.rerun()

        if col2.button("No, Cancel"):
            st.session_state["pending_action"] = None
            st.rerun()

if st.session_state.get("pending_action"):
    show_confirmation_dialog()

# --- PERSISTENT AUTHENTICATION ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if st.query_params.get("auth") == PASSWORD:
    st.session_state["authenticated"] = True

if not st.session_state["authenticated"]:
    st.title("Panel Shop Inventory Login")
    user_pass = st.text_input("Enter Shop Password:", type="password")
    
    col_auth1, col_auth2 = st.columns([1, 2])
    if col_auth1.button("Login", type="primary"):
        if user_pass == PASSWORD:
            st.session_state["authenticated"] = True
            st.query_params["auth"] = PASSWORD
            st.rerun()
        else:
            st.error("Incorrect Password. Access Denied.")
    st.stop()

st.title("Panel Shop Inventory System")
df = load_permanent_data()
location_dict = load_locations()

# Order dataframe columns strictly as requested
display_cols_order = ['Part Name', 'Part Number', 'Manufacturer', 'Qty on Hand', 'Location', 'Project Under', 'PO Number', 'Min Qty', 'Part Type']
if 'id' in df.columns:
    active_df = df[['id'] + display_cols_order].copy()
else:
    active_df = df[display_cols_order].copy()

# 9 MAIN TABS
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "Scan Search", 
    "Location Search",
    "Project & PO Search",
    "Receive / Add Stock", 
    "Take Inventory", 
    "Alter Part & Projects",
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
        "Click here to SCAN a barcode, or TYPE part details (Name, Number, Manufacturer, Type, PO#):", 
        key="search_input"
    ).strip()
    
    if search_query:
        results = fuzzy_search_df(active_df, search_query)
        
        if not results.empty:
            st.success(f"Found {len(results)} matching item(s):")
            for idx, row in results.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([1.8, 1.8, 1.4, 1.0, 1.4, 1.4, 1.2, 1.1])
                    
                    with col1:
                        st.caption("Part Name")
                        st.markdown(f"### {row['Part Name']}")
                    with col2:
                        st.caption("Part Number")
                        st.markdown(f"### `{row['Part Number']}`")
                    with col3:
                        st.caption("Manufacturer")
                        st.markdown(f"**{format_na_str(row.get('Manufacturer'))}**")
                    with col4:
                        st.caption("Quantity")
                        st.markdown(f"### {int(row['Qty on Hand'])}")
                    with col5:
                        loc_cat = get_location_category(str(row['Location']), location_dict)
                        st.caption("Location")
                        st.markdown(f"### [{row['Location']}] *({loc_cat})*")
                    with col6:
                        st.caption("Project / PO#")
                        st.markdown(f"**Proj:** {row['Project Under']}\n\n**PO#:** {format_na_str(row.get('PO Number'))}")
                    with col7:
                        st.caption("Part Type")
                        st.markdown(f"**{row['Part Type'] if row.get('Part Type') else 'N/A'}**")
                    with col8:
                        st.caption("Min Limit")
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

# --- TAB 2: LOCATION SEARCH & STORAGE MANAGEMENT ---
with tab2:
    st.header("Search Database by Storage Location")
    
    col_l1, col_l2 = st.columns(2)
    selected_floor = col_l1.selectbox("Filter by Floor Category:", ["Select a Floor Filter...", "Downstairs", "Upstairs"], key="floor_select")
    loc_search_query = col_l2.text_input("Or TYPE Specific Location Code (e.g. C3, G1, J2):", key="loc_search_input").strip().upper()
    
    has_location_filter = False
    results = active_df.copy()
    
    if selected_floor == "Downstairs":
        downstairs_codes = [code for code, cat in location_dict.items() if cat == "Downstairs"]
        results = results[results['Location'].astype(str).str.upper().isin(downstairs_codes) | results['Location'].astype(str).str.upper().str.match(r"^[A-F]")]
        has_location_filter = True
    elif selected_floor == "Upstairs":
        upstairs_codes = [code for code, cat in location_dict.items() if cat == "Upstairs"]
        results = results[results['Location'].astype(str).str.upper().isin(upstairs_codes) | results['Location'].astype(str).str.upper().str.match(r"^[G-I]")]
        has_location_filter = True
        
    if loc_search_query:
        norm_loc = normalize_str(loc_search_query)
        results = results[results['Location'].apply(normalize_str) == norm_loc]
        has_location_filter = True
        
    if has_location_filter:
        if not results.empty:
            st.success(f"Found {len(results)} item(s) in selected location filter:")
            for idx, row in results.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([1.8, 1.8, 1.4, 1.0, 1.4, 1.4, 1.2, 1.1])
                    
                    with col1:
                        st.caption("Part Name")
                        st.markdown(f"### {row['Part Name']}")
                    with col2:
                        st.caption("Part Number")
                        st.markdown(f"### `{row['Part Number']}`")
                    with col3:
                        st.caption("Manufacturer")
                        st.markdown(f"**{format_na_str(row.get('Manufacturer'))}**")
                    with col4:
                        st.caption("Quantity")
                        st.markdown(f"### {int(row['Qty on Hand'])}")
                    with col5:
                        loc_cat = get_location_category(str(row['Location']), location_dict)
                        st.caption("Location")
                        st.markdown(f"### [{row['Location']}] *({loc_cat})*")
                    with col6:
                        st.caption("Project / PO#")
                        st.markdown(f"**Proj:** {row['Project Under']}\n\n**PO#:** {format_na_str(row.get('PO Number'))}")
                    with col7:
                        st.caption("Part Type")
                        st.markdown(f"**{row['Part Type'] if row.get('Part Type') else 'N/A'}**")
                    with col8:
                        st.caption("Min Limit")
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
            st.warning("No items found matching the selected location criteria.")
    else:
        st.info("💡 Select a floor category or type a location code above to view stored parts.")

    st.markdown("---")
    
    with st.expander("➕ Register New Storage Section", expanded=False):
        st.write("Register a new alphabetical storage section with shelves:")
        col_n1, col_n2, col_n3 = st.columns(3)
        new_sec_letter = col_n1.text_input("Section Letter (e.g. J, K, L):", max_chars=2, key="add_sec_letter").strip().upper()
        new_sec_shelves = col_n2.number_input("Number of Shelves (e.g. 4 creates J1-J4):", min_value=1, max_value=20, value=3, key="add_sec_shelves")
        new_sec_cat = col_n3.selectbox("Floor Level:", ["Downstairs", "Upstairs"], key="add_sec_cat")
        
        if st.button("Save New Storage Section"):
            if not new_sec_letter or not new_sec_letter.isalpha():
                st.error("Please enter a valid alphabetical letter.")
            else:
                st.session_state["pending_action"] = {
                    "type": "add_location",
                    "letter": new_sec_letter,
                    "shelves": new_sec_shelves,
                    "category": new_sec_cat
                }
                st.rerun()

    all_known_letters = sorted(list(set([re.match(r"^([A-Z]+)", k).group(1) for k in location_dict.keys() if re.match(r"^([A-Z]+)", k)])))
    with st.expander("✏️ Alter Existing Storage Section", expanded=False):
        st.write("Modify shelf count or move an entire section between Upstairs/Downstairs:")
        col_alt1, col_alt2, col_alt3 = st.columns(3)
        selected_alt_letter = col_alt1.selectbox("Select Storage Section Letter to Alter:", all_known_letters, key="alter_sec_select")
        
        curr_codes = [c for c in location_dict.keys() if re.match(rf"^{selected_alt_letter}[0-9]+$", c)]
        curr_shelves = len(curr_codes) if curr_codes else 3
        curr_cat = location_dict.get(f"{selected_alt_letter}1", "Downstairs")
        
        new_alt_shelves = col_alt2.number_input("Update Number of Shelves:", min_value=1, max_value=20, value=curr_shelves, key="alter_sec_shelves")
        new_alt_cat = col_alt3.selectbox("Update Floor Level:", ["Downstairs", "Upstairs"], index=0 if curr_cat == "Downstairs" else 1, key="alter_sec_cat")
        
        if st.button("Save Storage Section Alterations"):
            st.session_state["pending_action"] = {
                "type": "alter_location",
                "letter": selected_alt_letter,
                "shelves": new_alt_shelves,
                "category": new_alt_cat,
                "loc_dict": location_dict
            }
            st.rerun()

    with st.expander("🗑️ Delete Empty Storage Section", expanded=False):
        st.write("Permanently remove a storage section. **(Must be 100% empty of parts to delete)**")
        col_del1, col_del2 = st.columns([2, 1])
        selected_del_letter = col_del1.selectbox("Select Storage Section Letter to Delete:", all_known_letters, key="del_sec_select")
        
        if col_del2.button("Delete Storage Section"):
            matching_parts = active_df[active_df['Location'].astype(str).str.upper().str.match(rf"^{selected_del_letter}[0-9]+$")]
            
            if not matching_parts.empty:
                st.error(f"⛔ CANNOT DELETE SECTION {selected_del_letter}! There are currently {len(matching_parts)} active part(s) stored here. Please move or remove all parts before deleting.")
            else:
                st.session_state["pending_action"] = {
                    "type": "delete_location",
                    "letter": selected_del_letter,
                    "loc_dict": location_dict
                }
                st.rerun()

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
                    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([1.8, 1.8, 1.4, 1.0, 1.4, 1.4, 1.2, 1.1])
                    
                    with col1:
                        st.caption("Part Name")
                        st.markdown(f"### {row['Part Name']}")
                    with col2:
                        st.caption("Part Number")
                        st.markdown(f"### `{row['Part Number']}`")
                    with col3:
                        st.caption("Manufacturer")
                        st.markdown(f"**{format_na_str(row.get('Manufacturer'))}**")
                    with col4:
                        st.caption("Quantity")
                        st.markdown(f"### {int(row['Qty on Hand'])}")
                    with col5:
                        loc_cat = get_location_category(str(row['Location']), location_dict)
                        st.caption("Location")
                        st.markdown(f"### [{row['Location']}] *({loc_cat})*")
                    with col6:
                        st.caption("Project / PO#")
                        st.markdown(f"**Proj:** {row['Project Under']}\n\n**PO#:** {format_na_str(row.get('PO Number'))}")
                    with col7:
                        st.caption("Part Type")
                        st.markdown(f"**{row['Part Type'] if row.get('Part Type') else 'N/A'}**")
                    with col8:
                        st.caption("Min Limit")
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

# --- TAB 4: RECEIVE / ADD STOCK (DIRECT ADD & SEPARATE STOCK FLOW) ---
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
        is_checked = st.checkbox("Register a Brand New Item (Not yet in database)", value=st.session_state["show_new_part_form"], key="new_item_chk")
        st.session_state["show_new_part_form"] = is_checked
        show_new_form = is_checked

    # 1. BRAND NEW ITEM REGISTRATION
    if show_new_form:
        st.info("Register a brand new, previously unrecorded item:")
        
        new_num = st.text_input("Part Number:", value=add_query if add_query else "", key="new_part_num_input").strip()
        new_name = st.text_input("Part Name:", key="new_part_name_input").strip()
        
        col_m1, col_m2 = st.columns(2)
        known_mfgs = sorted([m for m in active_df['Manufacturer'].dropna().astype(str).unique() if m.strip() and m != "N/A"])
        mfg_options = ["N/A"] + known_mfgs + ["+ Add New Manufacturer"]
        selected_mfg_opt = col_m1.selectbox("Manufacturer:", options=mfg_options, key="new_mfg_select")
        new_mfg = col_m1.text_input("Enter New Manufacturer Name:", key="new_mfg_custom").strip() if selected_mfg_opt == "+ Add New Manufacturer" else selected_mfg_opt
        
        known_types = sorted([t for t in active_df['Part Type'].dropna().astype(str).unique() if t.strip()])
        type_options = known_types + ["+ Add New Part Type"]
        selected_type_opt = col_m2.selectbox("Part Type:", options=type_options, key="new_part_type_select")
        new_type = col_m2.text_input("Enter New Part Type Name:", key="new_part_type_custom").strip() if selected_type_opt == "+ Add New Part Type" else selected_type_opt
            
        new_qty = st.number_input("Initial Quantity:", min_value=1, step=10, value=10, key="new_part_qty_input")
        new_loc = st.text_input("Storage Location (Must be a registered section, e.g. A1, G3, J2):", key="new_part_loc_input").strip().upper()
        
        col_n1, col_n2 = st.columns(2)
        known_projs = sorted([p for p in active_df['Project Under'].dropna().astype(str).unique() if p.strip()])
        proj_options = known_projs + ["+ Add New Project"]
        selected_proj_opt = col_n1.selectbox("Project Under:", options=proj_options, key="new_proj_select")
        new_proj = col_n1.text_input("Enter New Project Name:", key="new_proj_custom").strip() if selected_proj_opt == "+ Add New Project" else selected_proj_opt

        known_pos = sorted([po for po in active_df['PO Number'].dropna().astype(str).unique() if po.strip() and po != "N/A"])
        po_options = ["N/A"] + known_pos + ["+ Add New PO Number"]
        selected_po_opt = col_n2.selectbox("PO Number Ordered Under (Optional):", options=po_options, key="new_po_select")
        new_po = col_n2.text_input("Enter New PO Number:", key="new_po_custom").strip() if selected_po_opt == "+ Add New PO Number" else selected_po_opt
        
        new_min_qty = st.number_input("Minimum Quantity Alert Threshold (Optional, set 0 for None):", min_value=0, step=10, value=0, key="new_part_min_qty")
        
        if st.button("Save Brand New Item"):
            valid, formatted_loc = is_valid_location(new_loc, location_dict)
            final_po = format_na_str(new_po)
            final_mfg = format_na_str(new_mfg)
            
            norm_new_pnum = normalize_str(new_num)
            norm_new_loc = normalize_str(formatted_loc)
            norm_new_proj = normalize_str(new_proj)
            
            existing_exact = active_df[
                (active_df['Part Number'].apply(normalize_str) == norm_new_pnum) &
                (active_df['Location'].apply(normalize_str) == norm_new_loc) &
                (active_df['Project Under'].apply(normalize_str) == norm_new_proj)
            ]
            
            if not new_num:
                st.error("Part Number is required.")
            elif not new_name:
                st.error("Part Name is required.")
            elif not new_type:
                st.error("Part Type is required.")
            elif not new_proj:
                st.error("Project Under is required.")
            elif not valid:
                st.error(f"⛔ Location '{new_loc}' is not registered! You must assign parts to an existing storage location (e.g. A1-I3) or register Section '{new_loc[:1]}' in Tab 2 first.")
            elif not existing_exact.empty:
                st.error(f"⛔ HALTED: Part `{new_num}` is already registered in Location [{formatted_loc}] under Project '{new_proj}'! Please select it from the list above to add units.")
            else:
                st.session_state["pending_action"] = {
                    "type": "add",
                    "is_new": True,
                    "pnum": new_num,
                    "pname": new_name,
                    "mfg": final_mfg,
                    "amt": new_qty,
                    "loc": formatted_loc,
                    "proj": new_proj,
                    "ptype": new_type,
                    "po": final_po,
                    "min_qty": new_min_qty,
                    "is_correction": False
                }
                st.rerun()

    # 2. EXISTING PART STOCK ADDITION & SEPARATE STOCK REGISTRATION
    elif not results.empty:
        if add_query:
            st.success(f"Found {len(results)} matching item(s):")
        
        # Strict row selection bound to row index and database ID
        options = [f"{row['Part Name']} (#{row['Part Number']}) | Mfg: {format_na_str(row['Manufacturer'])} | Type: {row['Part Type']} | Proj: {row['Project Under']} | PO#: {format_na_str(row['PO Number'])} | Qty: {row['Qty on Hand']} | Loc: {row['Location']} (ID: {row.get('id', 'N/A')})" for idx, row in results.iterrows()]
        choice = st.selectbox("Select the exact item row you are receiving stock for:", options, key="add_select")
        row_idx = results.index[options.index(choice)]
        
        target_id = active_df.at[row_idx, 'id'] if 'id' in active_df.columns else None
        base_pnum = active_df.at[row_idx, 'Part Number']
        base_pname = active_df.at[row_idx, 'Part Name']
        base_mfg = format_na_str(active_df.at[row_idx, 'Manufacturer'])
        base_ptype = active_df.at[row_idx, 'Part Type']
        curr_row_loc = str(active_df.at[row_idx, 'Location'])
        curr_row_proj = str(active_df.at[row_idx, 'Project Under'])
        curr_row_po = format_na_str(active_df.at[row_idx, 'PO Number'])
        current_qty = int(active_df.at[row_idx, 'Qty on Hand'])
        current_min_qty = int(active_df.at[row_idx, 'Min Qty'])
        
        st.markdown("---")
        
        # Checkbox to toggle registering separate stock (new location/project for same part)
        register_separate = st.checkbox("➕ Register separate stock (different location or project for this same part)", value=False, key="chk_reg_separate")
        
        if not register_separate:
            # DIRECT ADD FLOW (Locks to chosen part row)
            st.write(f"Receiving incoming units directly for **{base_pname}** (`{base_pnum}`):")
            st.write(f"- **Project:** `{curr_row_proj}` | **Location:** `[{curr_row_loc}]` | **Current Stock on Hand:** **{current_qty}** units")
            
            col_amt1, col_amt2 = st.columns(2)
            amt_to_add = col_amt1.number_input("How many units are you adding?", min_value=1, step=10, value=10, key="add_amt_direct")
            updated_min_qty = col_amt2.number_input("Update Minimum Quantity Threshold (Optional):", min_value=0, step=10, value=current_min_qty, key="add_min_qty_direct")
            is_corr = st.checkbox("System Count Correction (Inventory discrepancy true-up, not a new delivery)", key="add_corr_direct")
            
            if st.button("Confirm Addition", type="primary"):
                st.session_state["pending_action"] = {
                    "type": "add",
                    "is_new": False,
                    "target_id": target_id,
                    "pnum": base_pnum,
                    "pname": base_pname,
                    "mfg": base_mfg,
                    "amt": amt_to_add,
                    "loc": curr_row_loc,
                    "proj": curr_row_proj,
                    "ptype": base_ptype,
                    "po": curr_row_po,
                    "current_qty": current_qty,
                    "min_qty": updated_min_qty,
                    "is_correction": is_corr
                }
                st.rerun()
        else:
            # SEPARATE STOCK REGISTRATION FLOW
            st.info(f"Registering a new storage/project entry using specs from **{base_pname}** (`{base_pnum}`):")
            
            col_sep1, col_sep2 = st.columns(2)
            amt_to_add = col_sep1.number_input("Quantity for this new entry:", min_value=1, step=10, value=10, key="add_amt_sep")
            sep_min_qty = col_sep2.number_input("Minimum Quantity Alert Level:", min_value=0, step=10, value=0, key="add_min_qty_sep")
            
            col_sep_p, col_sep_po = st.columns(2)
            known_projs = sorted([p for p in active_df['Project Under'].dropna().astype(str).unique() if p.strip()])
            proj_opts = known_projs + ["+ Add New Project"]
            def_proj_idx = proj_opts.index(curr_row_proj) if curr_row_proj in proj_opts else 0
            selected_proj_opt = col_sep_p.selectbox("Project Under:", options=proj_opts, index=def_proj_idx, key="sep_proj_select")
            final_dest_proj = col_sep_p.text_input("Enter New Project Name:", key="sep_proj_custom").strip() if selected_proj_opt == "+ Add New Project" else selected_proj_opt
            
            known_pos = sorted([po for po in active_df['PO Number'].dropna().astype(str).unique() if po.strip() and po != "N/A"])
            po_opts = ["N/A"] + known_pos + ["+ Add New PO Number"]
            selected_po_opt = col_sep_po.selectbox("PO Number Ordered Under (Optional):", options=po_opts, key="sep_po_select")
            final_dest_po = col_sep_po.text_input("Enter New PO Number:", key="sep_po_custom").strip() if selected_po_opt == "+ Add New PO Number" else selected_po_opt
            
            final_dest_loc = st.text_input("New Storage Location:", value="", key="sep_loc_input").strip().upper()
            
            if st.button("Save Separate Stock Entry", type="primary"):
                valid, formatted_dest_loc = is_valid_location(final_dest_loc, location_dict)
                if not final_dest_proj:
                    st.error("Project Under is required.")
                elif not valid:
                    st.error(f"⛔ Location '{final_dest_loc}' is not registered! You must assign parts to an existing storage location (e.g. A1-I3) or register Section '{final_dest_loc[:1]}' in Tab 2 first.")
                else:
                    norm_pnum = normalize_str(base_pnum)
                    norm_loc = normalize_str(formatted_dest_loc)
                    norm_proj = normalize_str(final_dest_proj)
                    
                    match_existing = active_df[
                        (active_df['Part Number'].apply(normalize_str) == norm_pnum) &
                        (active_df['Location'].apply(normalize_str) == norm_loc) &
                        (active_df['Project Under'].apply(normalize_str) == norm_proj)
                    ]
                    
                    if not match_existing.empty:
                        st.error(f"⛔ Part `{base_pnum}` is already registered at [{formatted_dest_loc}] under Project '{final_dest_proj}'! Please uncheck 'Register separate stock' and select that row directly to add units.")
                    else:
                        st.session_state["pending_action"] = {
                            "type": "add",
                            "is_new": True,
                            "target_id": None,
                            "pnum": base_pnum,
                            "pname": base_pname,
                            "mfg": base_mfg,
                            "amt": amt_to_add,
                            "loc": formatted_dest_loc,
                            "proj": final_dest_proj,
                            "ptype": base_ptype,
                            "po": format_na_str(final_dest_po),
                            "current_qty": 0,
                            "min_qty": sep_min_qty,
                            "is_correction": False
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
        options = [f"{row['Part Name']} (#{row['Part Number']}) | Mfg: {format_na_str(row['Manufacturer'])} | Type: {row['Part Type']} | Proj: {row['Project Under']} | PO#: {format_na_str(row['PO Number'])} | Qty: {row['Qty on Hand']} | Loc: {row['Location']} (ID: {row.get('id', 'N/A')})" for idx, row in results.iterrows()]
        choice = st.selectbox("Select the exact item row you are pulling stock from:", options, key="take_select")
        row_idx = results.index[options.index(choice)]
        
        amt_to_sub = st.number_input("How many units are you removing?", min_value=1, step=10, value=10, key="take_amt")
        is_corr_take = st.checkbox("System Count Correction (Inventory discrepancy true-up)", key="take_correction_chk")
        
        if st.button("Confirm Removal"):
            target_id = active_df.at[row_idx, 'id'] if 'id' in active_df.columns else None
            current_stock = int(active_df.at[row_idx, 'Qty on Hand'])
            part_num = active_df.at[row_idx, 'Part Number']
            part_name = active_df.at[row_idx, 'Part Name']
            mfg_name = format_na_str(active_df.at[row_idx, 'Manufacturer'])
            proj_name = active_df.at[row_idx, 'Project Under']
            loc_name = active_df.at[row_idx, 'Location']
            p_type = active_df.at[row_idx, 'Part Type']
            min_threshold = int(active_df.at[row_idx, 'Min Qty'])
            
            st.session_state["pending_action"] = {
                "type": "take",
                "target_id": target_id,
                "pnum": part_num,
                "pname": part_name,
                "mfg": mfg_name,
                "amt": amt_to_sub,
                "loc": loc_name,
                "proj": proj_name,
                "ptype": p_type,
                "current_qty": current_stock,
                "min_qty": min_threshold,
                "is_correction": is_corr_take
            }
            st.rerun()

# --- TAB 6: ALTER PART & PROJECTS (WITH BULK PROJECT MANAGEMENT) ---
with tab6:
    st.header("Alter Part Attributes & Manage Projects")
    
    subtab_part, subtab_proj_transfer, subtab_proj_delete = st.tabs([
        "✏️ Alter Individual Part",
        "🔄 Bulk Transfer Project Items",
        "🗑️ Delete Project"
    ])
    
    # SUB-TAB 1: ALTER INDIVIDUAL PART
    with subtab_part:
        st.subheader("Edit Part Attributes & Auto-Merge")
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
            options = [f"{row['Part Name']} (#{row['Part Number']}) | Mfg: {format_na_str(row['Manufacturer'])} | Proj: {row['Project Under']} | PO#: {format_na_str(row['PO Number'])} | Qty: {row['Qty on Hand']} | Loc: {row['Location']} (ID: {row.get('id', 'N/A')})" for idx, row in results.iterrows()]
            choice = st.selectbox("Select the exact item to edit:", options, key="alter_select")
            row_idx = results.index[options.index(choice)]
            
            st.subheader(f"Editing Part: {active_df.at[row_idx, 'Part Number']}")
            
            target_id = active_df.at[row_idx, 'id'] if 'id' in active_df.columns else None
            orig_pnum = active_df.at[row_idx, 'Part Number']
            orig_loc = active_df.at[row_idx, 'Location']
            orig_proj = active_df.at[row_idx, 'Project Under']
            orig_qty = int(active_df.at[row_idx, 'Qty on Hand'])
            
            col_edit1, col_edit2 = st.columns(2)
            updated_pnum = col_edit1.text_input("Part Number:", value=str(orig_pnum))
            updated_name = col_edit2.text_input("Part Name:", value=str(active_df.at[row_idx, 'Part Name']))
            
            current_mfg = format_na_str(active_df.at[row_idx, 'Manufacturer'])
            known_mfgs = sorted([m for m in active_df['Manufacturer'].dropna().astype(str).unique() if m.strip() and m != "N/A"])
            if current_mfg != "N/A" and current_mfg not in known_mfgs:
                known_mfgs.append(current_mfg)
            mfg_options = ["N/A"] + known_mfgs + ["+ Add New Manufacturer"]
            default_mfg_idx = mfg_options.index(current_mfg) if current_mfg in mfg_options else 0
            col_mfg1, col_mfg2 = st.columns(2)
            selected_mfg_opt = col_mfg1.selectbox("Manufacturer:", options=mfg_options, index=default_mfg_idx, key="alter_mfg_select")
            updated_mfg = col_mfg1.text_input("Enter New Manufacturer Name:", key="alter_mfg_custom").strip() if selected_mfg_opt == "+ Add New Manufacturer" else selected_mfg_opt
                
            updated_min_qty = col_mfg2.number_input("Minimum Quantity Alert Threshold:", min_value=0, step=10, value=int(active_df.at[row_idx, 'Min Qty']))
            
            col_a1, col_a2, col_a3 = st.columns(3)
            current_proj = str(active_df.at[row_idx, 'Project Under'])
            known_projs = sorted([p for p in active_df['Project Under'].dropna().astype(str).unique() if p.strip()])
            if current_proj and current_proj not in known_projs:
                known_projs.append(current_proj)
            proj_options = known_projs + ["+ Add New Project"]
            default_proj_idx = proj_options.index(current_proj) if current_proj in proj_options else 0
            selected_proj_opt = col_a1.selectbox("Project Under:", options=proj_options, index=default_proj_idx, key="alter_proj_select")
            updated_project = col_a1.text_input("Enter New Project Name:", key="alter_proj_custom").strip() if selected_proj_opt == "+ Add New Project" else selected_proj_opt
            
            current_po = format_na_str(active_df.at[row_idx, 'PO Number'])
            known_pos = sorted([po for po in active_df['PO Number'].dropna().astype(str).unique() if po.strip() and po != "N/A"])
            if current_po != "N/A" and current_po not in known_pos:
                known_pos.append(current_po)
            po_options = ["N/A"] + known_pos + ["+ Add New PO Number"]
            default_po_idx = po_options.index(current_po) if current_po in po_options else 0
            selected_po_opt = col_a2.selectbox("PO Number Ordered Under (Optional):", options=po_options, index=default_po_idx, key="alter_po_select")
            updated_po = col_a2.text_input("Enter New PO Number:", key="alter_po_custom").strip() if selected_po_opt == "+ Add New PO Number" else selected_po_opt
            
            current_type = str(active_df.at[row_idx, 'Part Type']) if pd.notna(active_df.at[row_idx, 'Part Type']) else ""
            known_types = sorted([t for t in active_df['Part Type'].dropna().astype(str).unique() if t.strip()])
            if current_type and current_type not in known_types:
                known_types.append(current_type)
            type_options = known_types + ["+ Add New Part Type"]
            default_type_idx = type_options.index(current_type) if current_type in type_options else 0
            selected_type_opt = col_a3.selectbox("Part Type:", options=type_options, index=default_type_idx, key="alter_part_type_select")
            updated_type = col_a3.text_input("Enter New Part Type Name:", key="alter_part_type_custom").strip() if selected_type_opt == "+ Add New Part Type" else selected_type_opt
            
            if st.button("Save Altered Attributes", type="primary"):
                final_po = format_na_str(updated_po)
                final_mfg = format_na_str(updated_mfg)
                if not updated_pnum.strip():
                    st.error("Part Number is required.")
                elif not updated_type:
                    st.error("Part Type is required.")
                elif not updated_project:
                    st.error("Project Under is required.")
                else:
                    norm_new_pnum = normalize_str(updated_pnum)
                    norm_new_proj = normalize_str(updated_project)
                    norm_orig_loc = normalize_str(orig_loc)
                    
                    existing_match = active_df[
                        (active_df['Part Number'].apply(normalize_str) == norm_new_pnum) &
                        (active_df['Project Under'].apply(normalize_str) == norm_new_proj) &
                        (active_df['Location'].apply(normalize_str) == norm_orig_loc) &
                        (active_df['id'] != target_id)
                    ]
                    
                    if not existing_match.empty:
                        merge_idx = existing_match.index[0]
                        merge_target_id = existing_match.at[merge_idx, 'id']
                        dest_curr_qty = int(existing_match.at[merge_idx, 'Qty on Hand'])
                        dest_po = format_na_str(existing_match.at[merge_idx, 'PO Number'])
                        final_adopted_po = dest_po if dest_po != "N/A" else final_po
                        
                        st.session_state["pending_action"] = {
                            "type": "alter",
                            "target_id": target_id,
                            "merge_target_id": merge_target_id,
                            "merge_add_qty": orig_qty,
                            "dest_curr_qty": dest_curr_qty,
                            "orig_pnum": orig_pnum,
                            "new_pnum": updated_pnum.strip(),
                            "orig_loc": orig_loc,
                            "orig_proj": orig_proj,
                            "new_name": updated_name,
                            "new_mfg": final_mfg,
                            "new_min_qty": updated_min_qty,
                            "new_proj": updated_project,
                            "new_po": final_adopted_po,
                            "new_type": updated_type
                        }
                    else:
                        st.session_state["pending_action"] = {
                            "type": "alter",
                            "target_id": target_id,
                            "merge_target_id": None,
                            "orig_pnum": orig_pnum,
                            "new_pnum": updated_pnum.strip(),
                            "orig_loc": orig_loc,
                            "orig_proj": orig_proj,
                            "new_name": updated_name,
                            "new_mfg": final_mfg,
                            "new_min_qty": updated_min_qty,
                            "new_proj": updated_project,
                            "new_po": final_po,
                            "new_type": updated_type
                        }
                    st.rerun()

    # SUB-TAB 2: BULK TRANSFER PROJECT ITEMS
    with subtab_proj_transfer:
        st.subheader("Transfer Concluded Project Items to a New Project")
        st.info("Select a source project to view its assigned items. Uncheck any specific items you wish to leave in the source project.")
        
        all_unique_projs = sorted([p for p in active_df['Project Under'].dropna().astype(str).unique() if p.strip()])
        
        col_tp1, col_tp2 = st.columns(2)
        source_proj = col_tp1.selectbox("Select Source Project to Transfer FROM:", ["-- Select Project --"] + all_unique_projs, key="bulk_src_proj")
        
        dest_proj_options = ["+ Add New Project"] + [p for p in all_unique_projs if p != source_proj]
        selected_dest_opt = col_tp2.selectbox("Select Destination Project to Transfer TO:", dest_proj_options, key="bulk_dest_proj_select")
        if selected_dest_opt == "+ Add New Project":
            target_dest_proj = col_tp2.text_input("Enter New Destination Project Name:", key="bulk_dest_proj_custom").strip()
        else:
            target_dest_proj = selected_dest_opt
            
        if source_proj != "-- Select Project --":
            src_items = active_df[active_df['Project Under'] == source_proj].copy()
            
            if src_items.empty:
                st.warning(f"No items currently assigned to Project '{source_proj}'.")
            else:
                st.markdown(f"### Select Items to Transfer ({len(src_items)} item(s) found under '{source_proj}'):")
                
                selected_item_rows = []
                for idx, row in src_items.iterrows():
                    item_label = f"**{row['Part Name']}** (`{row['Part Number']}`) | Loc: [{row['Location']}] | Qty: {int(row['Qty on Hand'])} | PO#: {format_na_str(row['PO Number'])}"
                    is_selected = st.checkbox(item_label, value=True, key=f"chk_bulk_{row.get('id', idx)}")
                    if is_selected:
                        selected_item_rows.append(row.to_dict())
                        
                st.markdown("---")
                if st.button("Transfer Selected Items", type="primary"):
                    if not target_dest_proj:
                        st.error("Please enter or select a valid destination project.")
                    elif not selected_item_rows:
                        st.error("No items selected for transfer. Check at least one item box.")
                    else:
                        st.session_state["pending_action"] = {
                            "type": "transfer_project_bulk",
                            "src_proj": source_proj,
                            "dest_proj": target_dest_proj,
                            "items": selected_item_rows
                        }
                        st.rerun()

    # SUB-TAB 3: DELETE EMPTY PROJECT
    with subtab_proj_delete:
        st.subheader("Delete Project Records")
        st.info("Permanently delete a project from active records. **(Safety Guardrail: The project must have 0 active items assigned to it)**")
        
        all_unique_projs = sorted([p for p in active_df['Project Under'].dropna().astype(str).unique() if p.strip()])
        proj_to_delete = st.selectbox("Select Project to Delete:", ["-- Select Project --"] + all_unique_projs, key="delete_proj_select")
        
        if st.button("Delete Project", type="primary"):
            if proj_to_delete == "-- Select Project --":
                st.error("Please select a valid project to delete.")
            else:
                active_proj_items = active_df[active_df['Project Under'] == proj_to_delete]
                if not active_proj_items.empty:
                    st.error(f"⛔ CANNOT DELETE PROJECT '{proj_to_delete}'! There are currently {len(active_proj_items)} item(s) still assigned to it (e.g., `{active_proj_items.iloc[0]['Part Number']}`). Please transfer or disregard all items under this project before deleting.")
                else:
                    st.session_state["pending_action"] = {
                        "type": "delete_project",
                        "project": proj_to_delete
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
                    st.error(f"⛔ Location '{new_location.upper()}' is not registered! You must assign parts to an existing storage location (e.g. A1-I3) or register Section '{new_location[:1].upper()}' in Tab 2 first.")
                else:
                    target_id = active_df.at[row_idx, 'id'] if 'id' in active_df.columns else None
                    old_loc = active_df.at[row_idx, 'Location']
                    part_num = active_df.at[row_idx, 'Part Number']
                    part_name = active_df.at[row_idx, 'Part Name']
                    mfg_name = format_na_str(active_df.at[row_idx, 'Manufacturer'])
                    proj_name = active_df.at[row_idx, 'Project Under']
                    p_type = active_df.at[row_idx, 'Part Type']
                    
                    st.session_state["pending_action"] = {
                        "type": "move_part",
                        "target_id": target_id,
                        "part_num": part_num,
                        "part_name": part_name,
                        "mfg": mfg_name,
                        "old_loc": old_loc,
                        "new_loc": formatted_loc,
                        "proj_name": proj_name,
                        "p_type": p_type
                    }
                    st.rerun()

# --- TAB 8: LOG HISTORY (WITH PART SEARCH & CALENDAR PICKER) ---
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
        
        # Individual part search input in Log History
        log_search_query = st.text_input("Search Logs by Part Name, Part Number, Manufacturer, Project, or Details:", key="log_search_input").strip()
        
        col_cal1, col_cal2 = st.columns([1.5, 2.5])
        selected_date = col_cal1.date_input(
            "Filter logs by calendar date:",
            value=None,
            min_value=min_date,
            max_value=today_date,
            key="log_calendar_picker"
        )
        if col_cal2.button("Clear Date Filter / Show All History"):
            st.rerun()

        col_l1, col_l2, col_l3 = st.columns(3)
        action_filter = col_l1.selectbox("Filter by Action:", ["All", "Added", "Removed", "Corrected (+)", "Corrected (-)", "Compiled / Merged", "Moved", "Altered", "Disregarded", "Added Location", "Altered Location", "Deleted Location", "Deleted Project"])
        log_proj_filter = col_l2.selectbox("Filter by Project Under:", ["All Projects"] + sorted(list(set(log_df['Project Under'].dropna().astype(str).unique()))))
        log_type_filter = col_l3.selectbox("Filter by Part Type:", ["All Part Types"] + sorted([t for t in log_df['Part Type'].dropna().astype(str).unique() if t.strip()]))
        
        filtered_logs = log_df.copy()
        
        if log_search_query:
            norm_q = normalize_str(log_search_query)
            mask = (
                filtered_logs['Part Number'].apply(normalize_str).str.contains(norm_q, na=False) |
                filtered_logs['Part Name'].apply(normalize_str).str.contains(norm_q, na=False) |
                filtered_logs['Manufacturer'].apply(normalize_str).str.contains(norm_q, na=False) |
                filtered_logs['Project Under'].apply(normalize_str).str.contains(norm_q, na=False) |
                filtered_logs['Details'].apply(normalize_str).str.contains(norm_q, na=False)
            )
            filtered_logs = filtered_logs[mask]
            
        if selected_date is not None:
            filtered_logs = filtered_logs[filtered_logs['Timestamp_DT'].dt.date == selected_date]
            st.caption(f"Showing logs recorded on **{selected_date.strftime('%B %d, %Y')}**:")
            
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

# --- SIDEBAR: LOW / OUT OF STOCK TABLE ---
st.sidebar.markdown("---")
st.sidebar.header("⚠️ Low / Out of Stock Items")

low_stock_mask = (active_df['Qty on Hand'] <= active_df['Min Qty']) | (active_df['Qty on Hand'] == 0)
low_stock_df = active_df[low_stock_mask].copy()

if low_stock_df.empty:
    st.sidebar.success("No active low/out-of-stock items needing restock.")
else:
    display_df = low_stock_df[['id', 'Part Name', 'Part Number', 'Manufacturer', 'Qty on Hand', 'Location', 'PO Number', 'Project Under']].copy()
    display_df['PO Number'] = display_df['PO Number'].apply(format_na_str)
    display_df['Manufacturer'] = display_df['Manufacturer'].apply(format_na_str)
    
    display_df.insert(0, "Disregard", False)
    display_df['Order Qty'] = 0
    
    edited_df = st.sidebar.data_editor(
        display_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "id": None,
            "Disregard": st.column_config.CheckboxColumn(
                "Disregard",
                help="Check to remove item permanently from active list",
                default=False
            ),
            "Part Name": st.column_config.TextColumn("Part Name", disabled=True),
            "Part Number": st.column_config.TextColumn("Part Number", disabled=True),
            "Manufacturer": st.column_config.TextColumn("Manufacturer", disabled=True),
            "Qty on Hand": st.column_config.NumberColumn("Current Qty", disabled=True),
            "Location": st.column_config.TextColumn("Loc", disabled=True),
            "PO Number": st.column_config.TextColumn("PO Under", help="Click to edit PO#; leaving blank sets to N/A"),
            "Project Under": st.column_config.TextColumn("Project Under", disabled=True),
            "Order Qty": st.column_config.NumberColumn("Order Qty", min_value=0, step=1, help="Type quantity needed for purchase email")
        },
        key="low_stock_editor"
    )
    
    for idx, r in edited_df.iterrows():
        current_entered_po = format_na_str(r['PO Number'])
        original_po = display_df.loc[idx, 'PO Number']
        if current_entered_po != original_po:
            target_id = r.get('id')
            p_num = r['Part Number']
            p_proj = r['Project Under']
            p_loc = r['Location']
            
            query = supabase.table("Inventory").update({"PO Number": current_entered_po})
            if target_id is not None and pd.notna(target_id):
                query = query.eq("id", target_id)
            else:
                query = query.eq("Part Number", str(p_num)).eq("Project Under", str(p_proj)).eq("Location", str(p_loc))
            query.execute()
            log_event("Altered", p_num, r['Part Name'], f"Updated PO# from {original_po} to {current_entered_po}", project_under=p_proj, manufacturer=r['Manufacturer'])
            st.rerun()

    # Generate Clipboard Text including typed Order Qty
    copy_text_lines = ["Part Name\tPart Number\tManufacturer\tCurrent Qty\tLocation\tPO Under\tProject Under\tOrder Qty"]
    for _, r in edited_df.iterrows():
        order_val = int(r['Order Qty']) if pd.notna(r['Order Qty']) and r['Order Qty'] > 0 else ""
        po_val = format_na_str(r['PO Number'])
        mfg_val = format_na_str(r['Manufacturer'])
        copy_text_lines.append(f"{r['Part Name']}\t{r['Part Number']}\t{mfg_val}\t{int(r['Qty on Hand'])}\t{r['Location']}\t{po_val}\t{r['Project Under']}\t{order_val}")
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
            disregarded_rows_to_process.append(row_data)
            
        disregarded_df_to_process = pd.DataFrame(disregarded_rows_to_process)
        
        if st.sidebar.button("Confirm Disregard Selected"):
            st.session_state["pending_action"] = {
                "type": "disregard",
                "rows": disregarded_df_to_process
            }
            st.rerun()

# --- Sidebar Footer & Log Out Option ---
st.sidebar.markdown("---")
if st.sidebar.button("🔒 Log Out", use_container_width=True):
    st.session_state["authenticated"] = False
    st.query_params.clear()
    st.rerun()

st.sidebar.markdown(
    """
    <div style='text-align: center; color: gray; font-size: 0.8em;'>
        <b>Panel Shop Inventory System v2.0</b><br>
        Built & Designed by <b>Zhou Czornoba</b><br>
        Co-op Term May-August 2026
    </div>
    """, 
    unsafe_allow_html=True
)
