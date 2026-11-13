
import httpx
import pandas as pd
import streamlit as st


# ==========================================
# CONFIGURATION
# ==========================================

API_BASE_URL = "http://127.0.0.1:8000/api/v1"

st.set_page_config(
    page_title="EmployeeFlow",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown("""
<style>

/* Make only the selectbox dropdown scrollable */
div[data-baseweb="popover"] [role="listbox"] {
    max-height: 280px !important;
    overflow-y: auto !important;
    overscroll-behavior: contain;
}

/* Dropdown scrollbar */
div[data-baseweb="popover"] [role="listbox"]::-webkit-scrollbar {
    width: 7px;
}

div[data-baseweb="popover"] [role="listbox"]::-webkit-scrollbar-thumb {
    background: #888;
    border-radius: 10px;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# API CONNECTION
# ==========================================

def get_api_data(endpoint, params=None):
    try:
        response = httpx.get(
            f"{API_BASE_URL}{endpoint}",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    except httpx.HTTPError as error:
        st.error(f"Backend connection error: {error}")
        return None


def post_api_data(endpoint, payload):
    """Send POST requests to the EmployeeFlow API."""
    try:
        response = httpx.post(
            f"{API_BASE_URL}{endpoint}",
            json=payload,
            timeout=10,
        )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            data = exc.response.json()
            detail = (
                data.get("detail", data)
                if isinstance(data, dict)
                else data
            )
        except ValueError:
            detail = exc.response.text

        st.error(
            f"API Error ({exc.response.status_code}): {detail}"
        )

    except httpx.RequestError as exc:
        st.error(f"Could not connect to EmployeeFlow API: {exc}")

    return None


# ==========================================
# SIDEBAR
# ==========================================


st.sidebar.title("🏢 EmployeeFlow")
st.sidebar.caption("Intelligent Leave & Expense Management")

st.sidebar.divider()

# Add space so the dropdown opens upwards
st.sidebar.markdown(
    "<div style='height: 85px;'></div>",
    unsafe_allow_html=True
)

page = st.sidebar.selectbox(
    "Navigation",
    [
        "Dashboard",
        "Employees",
        "Leave Management",
        "Expense Management",
        "Approval Center",
        "Exception Management",
        "Analytics"
    ],
    key="main_navigation"
)

st.sidebar.divider()
st.sidebar.caption("Powered by FastAPI + Streamlit")

# ==========================================
# DASHBOARD PAGE
# ==========================================

if page == "Dashboard":

    st.title("EmployeeFlow Dashboard")

    st.caption(
        "Overview of workforce, leave management, "
        "expenses, and reimbursements."
    )

    data = get_api_data("/dashboard/summary")

    if data:

        st.success("Connected to EmployeeFlow backend")

        st.subheader("Workforce Overview")

        col1, col2 = st.columns(2)

        col1.metric(
            "Total Employees",
            data["total_employees"],
        )

        col2.metric(
            "Active Employees",
            data["active_employees"],
        )

        st.divider()

        st.subheader("Leave Management")

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric("Total Requests", data["total_leave_requests"])
        col2.metric("Pending", data["pending_leave_requests"])
        col3.metric("Needs Review", data["leave_requests_needs_review"])
        col4.metric("Approved", data["approved_leave_requests"])
        col5.metric("Rejected", data["rejected_leave_requests"])

        st.divider()

        st.subheader("Expense Management")

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric("Total Claims", data["total_expense_claims"])
        col2.metric("Pending", data["pending_expense_claims"])
        col3.metric("Needs Review", data["expense_claims_needs_review"])
        col4.metric("Approved", data["approved_expense_claims"])
        col5.metric("Rejected", data["rejected_expense_claims"])

        st.divider()

        st.subheader("Reimbursement Overview")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Total Reimbursements",
            data["total_reimbursements"],
        )

        col2.metric(
            "Pending Payment",
            data["pending_reimbursements"],
        )

        col3.metric(
            "Paid",
            data["paid_reimbursements"],
        )

        st.divider()

        st.caption("EmployeeFlow | Live backend information")


# ==========================================
# EMPLOYEES PAGE
# ==========================================

elif page == "Employees":

    st.title("Employee Directory")

    st.caption(
        "Search, browse, and filter your organization's employees."
    )

    st.divider()

    # Search and filters
    st.subheader("Search & Filters")

    col1, col2, col3 = st.columns(3)

    with col1:
        search = st.text_input(
            "Search employee",
            placeholder="Name, ID, or email",
        )

    with col2:
        country = st.selectbox(
            "Country",
            ["All", "IN", "US"],
        )

    with col3:
        department = st.text_input(
            "Department",
            placeholder="Enter department",
        )

    col1, col2, col3 = st.columns(3)

    with col1:
        employment_status = st.selectbox(
            "Employment Status",
            [
                "All",
                "active",
                "on_leave",
                "terminated",
            ],
        )

    with col2:
        system_role = st.selectbox(
            "System Role",
            [
                "All",
                "employee",
                "manager",
                "hr_admin",
                "finance_admin",
                "operations_analyst",
                "system_admin",
            ],
        )

    with col3:
        page_size = st.selectbox(
            "Records per page",
            [10, 20, 50, 100],
            index=1,
        )

    # Build API query parameters
    params = {
        "page": 1,
        "page_size": page_size,
    }

    if search.strip():
        params["search"] = search.strip()

    if country != "All":
        params["country"] = country

    if department.strip():
        params["department"] = department.strip()

    if employment_status != "All":
        params["employment_status"] = employment_status

    if system_role != "All":
        params["system_role"] = system_role

    # Retrieve employees
    result = get_api_data(
        "/employees",
        params=params,
    )

    if result:

        total = result["total"]
        total_pages = result["total_pages"]

        st.divider()

        col1, col2 = st.columns(2)

        col1.metric("Matching Employees", total)
        col2.metric("Total Pages", total_pages)

        # Pagination
        selected_page = 1

        if total_pages > 1:

            selected_page = st.selectbox(
                "Select Page",
                options=list(range(1, total_pages + 1)),
            )

        if selected_page != 1:

            params["page"] = selected_page

            result = get_api_data(
                "/employees",
                params=params,
            )

        if result:

            employees = result["items"]

            if employees:

                employee_rows = []

                for employee in employees:

                    employee_rows.append({
                        "Employee ID": employee["employee_id"],
                        "Name": (
                            employee["first_name"]
                            + " "
                            + employee["last_name"]
                        ),
                        "Email": employee["email"],
                        "Department": employee["department"],
                        "Job Title": employee["job_title"],
                        "Country": employee["country_code"],
                        "Manager ID": employee["manager_employee_id"],
                        "Status": employee["employment_status"],
                        "Role": employee["system_role"],
                    })

                st.subheader("Employee Records")

                st.dataframe(
                    pd.DataFrame(employee_rows),
                    use_container_width=True,
                    hide_index=True,
                )

                st.caption(
                    f"Showing {len(employees)} employees "
                    f"on page {result['page']} of "
                    f"{result['total_pages']}."
                )

            else:
                st.info("No employees found for the selected filters.")
                
    
# ==========================================
# LEAVE MANAGEMENT PAGE
# ==========================================

elif page == "Leave Management":

    st.title("Leave Management")

    st.caption(
        "Monitor employee leave balances, requests, "
        "and approval history."
    )

    st.divider()

    # ------------------------------------------
    # LEAVE BALANCES
    # ------------------------------------------

    st.subheader("Employee Leave Balances")

    employee_id = st.text_input(
        "Enter Employee ID",
        placeholder="Example: EMP-000001",
        key="leave_employee_id",
    )

    if employee_id.strip():

        balances = get_api_data(
            f"/leave/balances/{employee_id.strip()}"
        )

        if balances is not None:

            if balances:

                st.success(
                    f"Leave balances found for {employee_id.upper()}"
                )

                balance_rows = []

                for balance in balances:

                    balance_rows.append({
                        "Policy ID": balance["leave_policy_id"],
                        "Year": balance["period_year"],
                        "Opening Days": balance["opening_days"],
                        "Accrued Days": balance["accrued_days"],
                        "Used Days": balance["approved_used_days"],
                        "Pending Reserved": balance["pending_reserved_days"],
                        "Available Days": balance["available_days"],
                    })

                st.dataframe(
                    pd.DataFrame(balance_rows),
                    use_container_width=True,
                    hide_index=True,
                )

            else:
                st.info("No leave balances found.")

    else:
        st.info(
            "Enter an employee ID to view their leave balances."
        )

    st.divider()

    # ------------------------------------------
    # LEAVE REQUESTS
    # ------------------------------------------

    st.subheader("Leave Requests")

    col1, col2, col3 = st.columns(3)

    with col1:
        filter_employee = st.text_input(
            "Filter by Employee ID",
            placeholder="EMP-000001",
            key="leave_filter_employee",
        )

    with col2:
        filter_status = st.selectbox(
            "Request Status",
            [
                "All",
                "draft",
                "submitted",
                "pending_approval",
                "needs_review",
                "approved",
                "rejected",
                "cancelled",
            ],
        )

    with col3:
        page_size = st.selectbox(
            "Records per page",
            [10, 20, 50, 100],
            index=1,
            key="leave_page_size",
        )

    params = {
        "page": 1,
        "page_size": page_size,
    }

    if filter_employee.strip():
        params["employee_id"] = filter_employee.strip()

    if filter_status != "All":
        params["status"] = filter_status

    result = get_api_data(
        "/leave/requests",
        params=params,
    )

    if result:

        col1, col2 = st.columns(2)

        col1.metric(
            "Matching Leave Requests",
            result["total"],
        )

        col2.metric(
            "Total Pages",
            result["total_pages"],
        )

        selected_page = 1

        if result["total_pages"] > 1:

            selected_page = st.selectbox(
                "Select Page",
                options=list(
                    range(1, result["total_pages"] + 1)
                ),
                key="leave_request_page",
            )

        if selected_page != 1:

            params["page"] = selected_page

            result = get_api_data(
                "/leave/requests",
                params=params,
            )

        if result:

            requests = result["items"]

            if requests:

                request_rows = []

                for request in requests:

                    request_rows.append({
                        "Request ID": request["leave_request_id"],
                        "Employee ID": request["employee_id"],
                        "Policy ID": request["leave_policy_id"],
                        "Start Date": request["start_date"],
                        "End Date": request["end_date"],
                        "Business Days": request["business_days"],
                        "Status": request["status"],
                    })

                st.dataframe(
                    pd.DataFrame(request_rows),
                    use_container_width=True,
                    hide_index=True,
                )

                st.caption(
                    f"Page {result['page']} of "
                    f"{result['total_pages']}"
                )

                # ----------------------------------
                # REQUEST DETAILS AND APPROVALS
                # ----------------------------------

                st.divider()

                st.subheader("Request Details & Approval History")

                request_ids = [
                    request["leave_request_id"]
                    for request in requests
                ]

                selected_request = st.selectbox(
                    "Select a leave request",
                    request_ids,
                )

                if selected_request:

                    detail = get_api_data(
                        f"/leave/requests/{selected_request}"
                    )

                    if detail:

                        st.markdown("#### Request Information")

                        st.json(detail)

                    approvals = get_api_data(
                        f"/leave/requests/{selected_request}/approvals"
                    )

                    if approvals is not None:

                        st.markdown("#### Approval History")

                        if approvals:

                            approval_rows = []

                            for approval in approvals:

                                approval_rows.append({
                                    "Step": approval["step_order"],
                                    "Approver ID": approval["approver_employee_id"],
                                    "Status": approval["status"],
                                    "Decision Reason": approval["decision_reason"],
                                    "Assigned At": approval["assigned_at"],
                                    "Decided At": approval["decided_at"],
                                })

                            st.dataframe(
                                pd.DataFrame(approval_rows),
                                use_container_width=True,
                                hide_index=True,
                            )

                        else:
                            st.info(
                                "No approval steps recorded for this request."
                            )

            else:
                st.info(
                    "No leave requests found for the selected filters."
                )

    
# ==========================================
# EXPENSE MANAGEMENT PAGE
# ==========================================

elif page == "Expense Management":

    st.title("Expense Management")

    st.caption(
        "Manage employee expense claims, expense lines, "
        "receipts, and approval history."
    )

    st.divider()
    

    # ------------------------------------------
    # SEARCH BY CLAIM ID
    # ------------------------------------------

    st.subheader("Find a Specific Expense Claim")

    with st.form("expense_claim_lookup_form"):

        lookup_col1, lookup_col2 = st.columns([4, 1])

        with lookup_col1:
            claim_id_lookup = st.text_input(
                "Expense Claim ID",
                placeholder="Example: EXP-2026-000944",
            )

        with lookup_col2:
            st.write("")
            lookup_submitted = st.form_submit_button(
                "Search Claim",
                use_container_width=True,
            )

    if lookup_submitted:

        if not claim_id_lookup.strip():

            st.warning("Please enter an expense claim ID.")

        else:

            claim_detail = get_api_data(
                f"/expenses/claims/{claim_id_lookup.strip().upper()}"
            )

            if claim_detail:

                st.success("Expense claim found!")

                currency = claim_detail["currency_code"]
                total_amount = claim_detail["total_amount_minor"] / 100

                if currency == "INR":
                    formatted_total = f"₹{total_amount:,.2f}"
                else:
                    formatted_total = f"{currency} {total_amount:,.2f}"

                col1, col2, col3 = st.columns(3)

                col1.metric("Claim Amount", formatted_total)

                col2.metric(
                    "Employee",
                    claim_detail["employee_id"],
                )

                col3.metric(
                    "Status",
                    claim_detail["status"].replace("_", " ").title(),
                )

                st.write(
                    "**Business Purpose:**",
                    claim_detail["business_purpose"],
                )

                # Expense line items
                st.markdown("#### Expense Line Items")

                lines = claim_detail["expense_lines"]

                if lines:

                    line_rows = []

                    for line in lines:

                        amount = line["amount_minor"] / 100

                        if currency == "INR":
                            formatted_amount = f"₹{amount:,.2f}"
                        else:
                            formatted_amount = f"{currency} {amount:,.2f}"

                        line_rows.append({
                            "Line": line["line_number"],
                            "Date": line["expense_date"],
                            "Category": line["category"],
                            "Merchant": line["merchant"],
                            "Description": line["description"],
                            "Amount": formatted_amount,
                            "Receipt": line["receipt_filename"] or "Missing",
                        })

                    st.dataframe(
                        pd.DataFrame(line_rows),
                        use_container_width=True,
                        hide_index=True,
                    )
                    
                    
                

                # Approval history
                st.markdown("#### Approval History")

                approvals = get_api_data(
                    f"/expenses/claims/{claim_id_lookup.strip().upper()}/approvals"
                )

                if approvals is not None:

                    if approvals:

                        approval_rows = []

                        for approval in approvals:

                            approval_rows.append({
                                "Step": approval["step_order"],
                                "Approver": approval["approver_employee_id"],
                                "Status": approval["status"],
                                "Decision": approval["decision_reason"],
                                "Assigned At": approval["assigned_at"],
                                "Decided At": approval["decided_at"],
                            })

                        st.dataframe(
                            pd.DataFrame(approval_rows),
                            use_container_width=True,
                            hide_index=True,
                        )

                    else:
                        st.info("No approval history available.")

    st.divider()


    # ------------------------------------------
    # SEARCH AND FILTERS
    # ------------------------------------------

    st.subheader("Search & Filters")

    col1, col2, col3 = st.columns(3)

    with col1:
        employee_filter = st.text_input(
            "Employee ID",
            placeholder="EMP-000001",
            key="expense_employee_filter",
        )

    with col2:
        country_filter = st.selectbox(
            "Country",
            ["All", "IN", "US"],
            key="expense_country_filter",
        )

    with col3:
        status_filter = st.selectbox(
            "Claim Status",
            [
                "All",
                "draft",
                "submitted",
                "pending_approval",
                "needs_review",
                "approved",
                "rejected",
                "cancelled",
            ],
            key="expense_status_filter",
        )

    col1, col2 = st.columns(2)

    with col1:
        category_filter = st.selectbox(
            "Expense Category",
            [
                "All",
                "travel",
                "meals",
                "accommodation",
                "office_supplies",
                "software",
                "training",
            ],
            key="expense_category_filter",
        )

    with col2:
        page_size = st.selectbox(
            "Records per page",
            [10, 20, 50, 100],
            index=1,
            key="expense_page_size",
        )

    # ------------------------------------------
    # BUILD API PARAMETERS
    # ------------------------------------------

    params = {
        "page": 1,
        "page_size": page_size,
    }

    if employee_filter.strip():
        params["employee_id"] = employee_filter.strip()

    if country_filter != "All":
        params["country_code"] = country_filter

    if status_filter != "All":
        params["status"] = status_filter

    if category_filter != "All":
        params["category"] = category_filter

    # ------------------------------------------
    # FETCH EXPENSE CLAIMS
    # ------------------------------------------

    result = get_api_data(
        "/expenses/claims",
        params=params,
    )

    if result is not None:

        st.divider()

        col1, col2 = st.columns(2)

        col1.metric(
            "Matching Expense Claims",
            result["total"],
        )

        col2.metric(
            "Total Pages",
            result["total_pages"],
        )

        # --------------------------------------
        # PAGINATION
        # --------------------------------------

        selected_page = 1

        if result["total_pages"] > 1:

            selected_page = st.selectbox(
                "Select Page",
                options=list(
                    range(1, result["total_pages"] + 1)
                ),
                key="expense_claim_page",
            )

        if selected_page != 1:

            params["page"] = selected_page

            result = get_api_data(
                "/expenses/claims",
                params=params,
            )

        if result is not None:

            claims = result["items"]

            if claims:

                # ----------------------------------
                # CLAIMS TABLE
                # ----------------------------------

                st.subheader("Expense Claims")

                claim_rows = []

                for claim in claims:

                    amount = claim["total_amount_minor"] / 100

                    if claim["currency_code"] == "INR":
                        formatted_amount = f"₹{amount:,.2f}"
                    else:
                        formatted_amount = (
                            f'{claim["currency_code"]} {amount:,.2f}'
                        )

                    claim_rows.append({
                        "Claim ID": claim["expense_claim_id"],
                        "Employee ID": claim["employee_id"],
                        "Country": claim["country_code"],
                        "Category": claim["primary_category"],
                        "Amount": formatted_amount,
                        "Start Date": claim["expense_start_date"],
                        "End Date": claim["expense_end_date"],
                        "Status": claim["status"],
                    })

                st.dataframe(
                    pd.DataFrame(claim_rows),
                    use_container_width=True,
                    hide_index=True,
                )

                st.caption(
                    f"Showing {len(claims)} claims "
                    f"on page {result['page']} of "
                    f"{result['total_pages']}."
                )

                # ----------------------------------
                # CLAIM DETAILS
                # ----------------------------------

                st.divider()

                st.subheader("Expense Claim Details")

                claim_ids = [
                    claim["expense_claim_id"]
                    for claim in claims
                ]

                selected_claim = st.selectbox(
                    "Select an expense claim",
                    claim_ids,
                    key="selected_expense_claim",
                )

                if selected_claim:

                    detail = get_api_data(
                        f"/expenses/claims/{selected_claim}"
                    )

                    if detail:

                        amount = detail["total_amount_minor"] / 100

                        if detail["currency_code"] == "INR":
                            formatted_total = f"₹{amount:,.2f}"
                        else:
                            formatted_total = (
                                f'{detail["currency_code"]} {amount:,.2f}'
                            )

                        col1, col2, col3 = st.columns(3)

                        col1.metric(
                            "Claim Amount",
                            formatted_total,
                        )

                        col2.metric(
                            "Expense Lines",
                            len(detail["expense_lines"]),
                        )

                        col3.metric(
                            "Claim Status",
                            detail["status"].replace("_", " ").title(),
                        )

                        st.markdown("#### Business Purpose")

                        st.write(detail["business_purpose"])

                        st.markdown("#### Claim Information")

                        info_col1, info_col2 = st.columns(2)

                        info_col1.write(
                            f'**Employee:** {detail["employee_id"]}'
                        )

                        info_col1.write(
                            f'**Cost Center:** {detail["cost_center_id"] or "Not assigned"}'
                        )

                        info_col2.write(
                            f'**Country:** {detail["country_code"]}'
                        )

                        info_col2.write(
                            f'**Currency:** {detail["currency_code"]}'
                        )

                        # ----------------------------------
                        # EXPENSE LINES
                        # ----------------------------------

                        st.divider()

                        st.markdown("#### Expense Line Items")

                        lines = detail["expense_lines"]

                        if lines:

                            line_rows = []

                            for line in lines:

                                line_amount = (
                                    line["amount_minor"] / 100
                                )

                                if detail["currency_code"] == "INR":
                                    formatted_line_amount = (
                                        f"₹{line_amount:,.2f}"
                                    )
                                else:
                                    formatted_line_amount = (
                                        f'{detail["currency_code"]} '
                                        f'{line_amount:,.2f}'
                                    )

                                line_rows.append({
                                    "Line": line["line_number"],
                                    "Date": line["expense_date"],
                                    "Category": line["category"],
                                    "Merchant": line["merchant"],
                                    "Description": line["description"],
                                    "Amount": formatted_line_amount,
                                    "Receipt": (
                                        line["receipt_filename"]
                                        or "Missing"
                                    ),
                                    "Receipt MIME Type": (
                                        line["receipt_mime_type"]
                                        or "N/A"
                                    ),
                                })

                            st.dataframe(
                                pd.DataFrame(line_rows),
                                use_container_width=True,
                                hide_index=True,
                            )

                        else:
                            st.info("No expense lines found.")

                        # ----------------------------------
                        # APPROVAL HISTORY
                        # ----------------------------------

                        st.divider()

                        st.markdown("#### Approval History")

                        approvals = get_api_data(
                            f"/expenses/claims/{selected_claim}/approvals"
                        )

                        if approvals is not None:

                            if approvals:

                                approval_rows = []

                                for approval in approvals:

                                    approval_rows.append({
                                        "Step": approval["step_order"],
                                        "Approver ID": approval["approver_employee_id"],
                                        "Status": approval["status"],
                                        "Decision Reason": approval["decision_reason"],
                                        "Assigned At": approval["assigned_at"],
                                        "Decided At": approval["decided_at"],
                                    })

                                st.dataframe(
                                    pd.DataFrame(approval_rows),
                                    use_container_width=True,
                                    hide_index=True,
                                )

                            else:
                                st.info(
                                    "No approval history available."
                                )

            else:
                st.info(
                    "No expense claims found for the selected filters."
                )


elif page == "Approval Center":

    st.title("Approval Center")
    st.caption(
        "Review, approve, or reject pending leave and expense requests."
    )

    # Show the result of the previous action after page refresh.
    if "approval_action_message" in st.session_state:
        st.success(
            st.session_state.pop("approval_action_message")
        )

    st.divider()

    # ------------------------------------------
    # FILTERS
    # ------------------------------------------

    st.subheader("Filter Approval Requests")

    col1, col2, col3 = st.columns(3)

    with col1:
        approver_id = st.text_input(
            "Approver Employee ID",
            placeholder="Example: EMP-000015",
        )

    with col2:
        request_type = st.selectbox(
            "Request Type",
            ["All", "Leave", "Expense"],
        )

    with col3:
        country = st.selectbox(
            "Country",
            ["All", "IN", "US"],
        )

    # ------------------------------------------
    # FETCH PENDING APPROVALS
    # ------------------------------------------

    params = {}

    if approver_id.strip():
        params["approver_employee_id"] = approver_id.strip().upper()

    if request_type != "All":
        params["request_type"] = request_type.lower()

    if country != "All":
        params["country_code"] = country

    approval_data = get_api_data(
        "/approvals/pending",
        params=params,
    )

    if approval_data is not None:

        items = approval_data.get("items", [])

        leave_count = sum(
            1 for item in items
            if item["request_type"] == "leave"
        )

        expense_count = sum(
            1 for item in items
            if item["request_type"] == "expense"
        )

        # --------------------------------------
        # SUMMARY METRICS
        # --------------------------------------

        st.subheader("Approval Overview")

        col1, col2, col3 = st.columns(3)

        col1.metric("Pending Approvals", len(items))
        col2.metric("Leave Approvals", leave_count)
        col3.metric("Expense Approvals", expense_count)

        st.divider()

        # --------------------------------------
        # APPROVAL TABLE
        # --------------------------------------

        st.subheader("Pending Approval Steps")

        if items:

            rows = []

            for item in items:

                amount = "-"

                if item["amount_minor"] is not None:

                    value = item["amount_minor"] / 100

                    if item["currency_code"] == "INR":
                        amount = f"₹{value:,.2f}"
                    else:
                        amount = (
                            f'{item["currency_code"]} {value:,.2f}'
                        )

                rows.append({
                    "Approval ID": item["approval_step_id"],
                    "Request ID": item["request_id"],
                    "Type": item["request_type"].title(),
                    "Requester": item["requester_name"],
                    "Employee ID": item["requester_employee_id"],
                    "Department": item["department"],
                    "Country": item["country_code"],
                    "Approver": item["approver_employee_id"],
                    "Step": item["step_order"],
                    "Summary": item["summary"],
                    "Start Date": item["start_date"],
                    "End Date": item["end_date"],
                    "Amount": amount,
                    "Status": item["status"].title(),
                })

            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )

            st.divider()

            # ----------------------------------
            # SELECT AN APPROVAL
            # ----------------------------------

            st.subheader("Process an Approval")

            item_by_id = {
                item["approval_step_id"]: item
                for item in items
            }

            approval_ids = list(item_by_id.keys())

            selected_approval_id = st.selectbox(
                "Select an approval request",
                options=approval_ids,
                format_func=lambda approval_id: (
                    f'{item_by_id[approval_id]["request_id"]} | '
                    f'{item_by_id[approval_id]["request_type"].title()} | '
                    f'{item_by_id[approval_id]["requester_name"]}'
                ),
                key="selected_approval_step",
            )

            selected_item = item_by_id[selected_approval_id]

            # ----------------------------------
            # SELECTED REQUEST DETAILS
            # ----------------------------------

            st.markdown("### Request Details")

            col1, col2, col3 = st.columns(3)

            col1.write("**Request ID**")
            col1.write(selected_item["request_id"])

            col2.write("**Requester**")
            col2.write(selected_item["requester_name"])

            col3.write("**Department**")
            col3.write(selected_item["department"])

            col1, col2, col3 = st.columns(3)

            col1.write("**Request Type**")
            col1.write(selected_item["request_type"].title())

            col2.write("**Country**")
            col2.write(selected_item["country_code"])

            col3.write("**Assigned Approver**")
            col3.write(selected_item["approver_employee_id"])

            st.write("**Summary:**", selected_item["summary"])

            if selected_item["amount_minor"] is not None:

                amount_value = selected_item["amount_minor"] / 100

                if selected_item["currency_code"] == "INR":
                    formatted_amount = f"₹{amount_value:,.2f}"
                else:
                    formatted_amount = (
                        f'{selected_item["currency_code"]} '
                        f'{amount_value:,.2f}'
                    )

                st.write("**Claim Amount:**", formatted_amount)

            else:
                st.write(
                    "**Leave Dates:**",
                    f'{selected_item["start_date"]} to '
                    f'{selected_item["end_date"]}'
                )

            st.divider()

            # ----------------------------------
            # AUTHORIZATION CHECK IN THE UI
            # ----------------------------------

            acting_approver_id = approver_id.strip().upper()

            assigned_approver_id = (
                selected_item["approver_employee_id"]
            )

            can_process = (
                bool(acting_approver_id)
                and acting_approver_id == assigned_approver_id
            )

            if not acting_approver_id:

                st.info(
                    "Enter the assigned approver's Employee ID "
                    "in the filter above to enable decisions."
                )

            elif not can_process:

                st.warning(
                    "The entered employee ID does not match "
                    "the assigned approver for this request."
                )

            else:

                st.success(
                    f"You are processing this request as "
                    f"{acting_approver_id}."
                )

            # ----------------------------------
            # DECISION REASON
            # ----------------------------------

            reason = st.text_area(
                "Decision Reason",
                placeholder=(
                    "Enter an explanation. A reason is mandatory "
                    "when rejecting a request."
                ),
                key=f"decision_reason_{selected_approval_id}",
            )

            col1, col2 = st.columns(2)

            # ----------------------------------
            # APPROVE
            # ----------------------------------

            with col1:

                if st.button(
                    "Approve Request",
                    type="primary",
                    use_container_width=True,
                    disabled=not can_process,
                    key=f"approve_{selected_approval_id}",
                ):

                    payload = {
                        "actor_employee_id": acting_approver_id,
                        "decision": "approve",
                        "reason": reason.strip() or None,
                    }

                    result = post_api_data(
                        f"/approvals/{selected_approval_id}/decision",
                        payload,
                    )

                    if result is not None:

                        st.session_state[
                            "approval_action_message"
                        ] = result.get(
                            "message",
                            "Request approved successfully."
                        )

                        st.rerun()

            # ----------------------------------
            # REJECT
            # ----------------------------------

            with col2:

                if st.button(
                    "Reject Request",
                    type="secondary",
                    use_container_width=True,
                    disabled=not can_process,
                    key=f"reject_{selected_approval_id}",
                ):

                    if not reason.strip():

                        st.error(
                            "Please provide a reason before rejecting."
                        )

                    else:

                        payload = {
                            "actor_employee_id": acting_approver_id,
                            "decision": "reject",
                            "reason": reason.strip(),
                        }

                        result = post_api_data(
                            f"/approvals/{selected_approval_id}/decision",
                            payload,
                        )

                        if result is not None:

                            st.session_state[
                                "approval_action_message"
                            ] = result.get(
                                "message",
                                "Request rejected successfully."
                            )

                            st.rerun()

        else:

            st.info("No pending approvals match your filters.")

    else:

        st.error(
            "Unable to retrieve approval requests. "
            "Check the API server."
        )
        
  
    # ==========================================
    # DECISION HISTORY
    # ==========================================

    st.divider()

    st.subheader("Approval Decision History")

    st.caption(
        "View previously approved, rejected, and skipped "
        "approval decisions."
    )

    # Decision status filter
    history_status = st.selectbox(
        "Filter by Decision",
        ["All", "Approved", "Rejected", "Skipped"],
        key="approval_history_status",
    )

    # Reuse the existing page filters
    history_params = dict(params)

    if history_status != "All":
        history_params["decision_status"] = history_status.lower()

    history_params["limit"] = 100

    # Fetch completed approval decisions
    history_data = get_api_data(
        "/approvals/history",
        params=history_params,
    )

    if history_data is not None:

        history_items = history_data.get("items", [])

        # Summary metrics
        approved_count = sum(
            1 for item in history_items
            if item["decision"] == "approved"
        )

        rejected_count = sum(
            1 for item in history_items
            if item["decision"] == "rejected"
        )

        skipped_count = sum(
            1 for item in history_items
            if item["decision"] == "skipped"
        )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Decisions Shown", len(history_items))
        col2.metric("Approved", approved_count)
        col3.metric("Rejected", rejected_count)
        col4.metric("Skipped", skipped_count)

        st.caption(
            "Counts reflect the latest 100 decisions displayed."
        )

        if history_items:

            history_rows = []

            for item in history_items:

                amount = "-"

                if item["amount_minor"] is not None:

                    value = item["amount_minor"] / 100

                    if item["currency_code"] == "INR":
                        amount = f"₹{value:,.2f}"
                    else:
                        amount = (
                            f'{item["currency_code"]} {value:,.2f}'
                        )

                history_rows.append({
                    "Approval ID": item["approval_step_id"],
                    "Request ID": item["request_id"],
                    "Type": item["request_type"].title(),
                    "Requester": item["requester_name"],
                    "Approver": (
                        f'{item["approver_name"]} '
                        f'({item["approver_employee_id"]})'
                    ),
                    "Step": item["step_order"],
                    "Decision": item["decision"].title(),
                    "Request Status": item["request_status"].title(),
                    "Decision Date": (
                        str(item["decided_at"])
                        if item["decided_at"]
                        else "-"
                    ),
                    "Reason": item["decision_reason"] or "-",
                    "Summary": item["summary"],
                    "Amount": amount,
                })

            st.dataframe(
                pd.DataFrame(history_rows),
                use_container_width=True,
                hide_index=True,
            )

            # Detailed history for a selected request
            st.divider()
            st.markdown("### View Approval Details")

            request_ids = list(dict.fromkeys(
                item["request_id"] for item in history_items
            ))

            selected_request_id = st.selectbox(
                "Select Request",
                request_ids,
                key="history_selected_request",
            )

            selected_history = [
                item for item in history_items
                if item["request_id"] == selected_request_id
            ]

            for item in selected_history:

                st.markdown(
                    f'**Step {item["step_order"]} — '
                    f'{item["approver_name"]}**'
                )

                st.write(
                    "Decision:",
                    item["decision"].upper(),
                )

                st.write(
                    "Reason:",
                    item["decision_reason"] or "-",
                )

                st.write(
                    "Decision Date:",
                    item["decided_at"] or "-",
                )

                st.divider()

            # Final request status
            final_status = selected_history[0]["request_status"]

            st.write(
                f"**Overall Request Status:** "
                f"{final_status.upper()}"
            )

        else:
            st.info(
                "No completed approval decisions match your filters."
            )

    else:
        st.warning(
            "Unable to retrieve approval history. "
            "Please check the API server."
        )


elif page == "Exception Management":

    st.title("Exception Management")
    st.caption(
        "Identify policy violations, missing information "
        "and unusual transactions."
    )

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        severity = st.selectbox(
            "Severity",
            ["All", "High", "Medium"]
        )

    with col2:
        exception_type = st.selectbox(
            "Exception Type",
            [
                "All",
                "missing_cost_center",
                "missing_receipt",
                "duplicate_receipt",
                "per_item_limit_breach",
                "out_of_employment_dates",
                "overlapping_approved_leave",
            ]
        )

    with col3:
        country = st.selectbox(
            "Country",
            ["All", "IN", "US"]
        )

    # Build API filters
    params = {}

    if severity != "All":
        params["severity"] = severity.lower()

    if exception_type != "All":
        params["exception_type"] = exception_type

    if country != "All":
        params["country_code"] = country

    # Retrieve exceptions
    exception_data = get_api_data(
        "/exceptions/",
        params=params
    )

    if exception_data is not None:

        items = exception_data.get("items", [])

        high_count = sum(
            1 for item in items
            if item["severity"] == "high"
        )

        medium_count = sum(
            1 for item in items
            if item["severity"] == "medium"
        )

        st.divider()
        st.subheader("Exception Overview")

        col1, col2, col3 = st.columns(3)

        col1.metric("Total Exceptions", len(items))
        col2.metric("High Severity", high_count)
        col3.metric("Medium Severity", medium_count)

        st.divider()
        st.subheader("Detected Exceptions")

        if items:

            rows = []

            for item in items:
                amount = "-"

                if item["amount_minor"] is not None:
                    value = item["amount_minor"] / 100

                    if item["currency_code"] == "INR":
                        amount = f"₹{value:,.2f}"
                    else:
                        amount = (
                            f'{item["currency_code"]} {value:,.2f}'
                        )

                rows.append({
                    "Exception ID": item["exception_id"],
                    "Type": item["exception_type"],
                    "Severity": item["severity"].upper(),
                    "Employee": item["employee_name"],
                    "Employee ID": item["employee_id"],
                    "Department": item["department"],
                    "Country": item["country_code"],
                    "Entity ID": item["entity_id"],
                    "Amount": amount,
                    "Description": item["description"],
                })

            st.dataframe(
                rows,
                use_container_width=True,
                hide_index=True
            )

            st.divider()
            st.subheader("Investigate an Exception")

            selected_id = st.selectbox(
                "Select Exception",
                [item["exception_id"] for item in items]
            )

            selected = next(
                item for item in items
                if item["exception_id"] == selected_id
            )

            st.markdown(
                f"### {selected['exception_type'].replace('_', ' ').title()}"
            )

            st.write(
                f"**Severity:** {selected['severity'].upper()}"
            )
            st.write(
                f"**Employee:** {selected['employee_name']} "
                f"({selected['employee_id']})"
            )
            st.write(
                f"**Department:** {selected['department']}"
            )
            st.write(
                f"**Entity:** {selected['entity_type']} — "
                f"{selected['entity_id']}"
            )
            st.write(
                f"**Description:** {selected['description']}"
            )

            if selected["related_id"]:
                st.write(
                    f"**Related record:** {selected['related_id']}"
                )

        else:
            st.success("No exceptions match the selected filters.")

    else:
        st.error("Unable to retrieve exceptions from the API.")



elif page == "Analytics":

    st.title("Analytics Dashboard")
    st.caption(
        "Business insights into workforce, expenses, "
        "reimbursements and policy exceptions."
    )

    summary = get_api_data("/dashboard/summary")
    analytics = get_api_data("/analytics/breakdown")

    if summary is None or analytics is None:
        st.error(
            "Unable to load analytics. "
            "Please check the API server."
        )

    else:

        # 1. Business Overview
        st.subheader("Business Overview")

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Total Employees",
            summary["total_employees"]
        )
        col2.metric(
            "Active Employees",
            summary["active_employees"]
        )
        col3.metric(
            "Leave Requests",
            summary["total_leave_requests"]
        )
        col4.metric(
            "Expense Claims",
            summary["total_expense_claims"]
        )

        st.divider()

        # 2. Workforce Analytics
        st.subheader("Workforce Distribution")

        country_df = pd.DataFrame(
            analytics["workforce_by_country"]
        )

        department_df = pd.DataFrame(
            analytics["workforce_by_department"]
        )

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Employees by Country**")

            if not country_df.empty:
                country_df["country"] = (
                    country_df["country_code"]
                    .map({
                        "IN": "India",
                        "US": "United States"
                    })
                    .fillna(country_df["country_code"])
                )

                st.bar_chart(
                    country_df.set_index("country")[
                        ["employee_count"]
                    ]
                )

        with col2:
            st.markdown("**Employees by Department**")

            if not department_df.empty:
                st.bar_chart(
                    department_df.set_index("department")[
                        ["employee_count"]
                    ]
                )

        st.divider()

        # 3. Leave Analytics
        st.subheader("Leave Request Analytics")

        leave_df = pd.DataFrame({
            "Status": [
                "Approved",
                "Pending",
                "Needs Review",
                "Rejected"
            ],
            "Count": [
                summary["approved_leave_requests"],
                summary["pending_leave_requests"],
                summary["leave_requests_needs_review"],
                summary["rejected_leave_requests"]
            ]
        })

        col1, col2 = st.columns(2)

        with col1:
            st.bar_chart(
                leave_df.set_index("Status")
            )

        with col2:
            st.dataframe(
                leave_df,
                use_container_width=True,
                hide_index=True
            )

        st.divider()

        # 4. Expense Analytics
        st.subheader("Approved Expense Spend")

        expense_df = pd.DataFrame(
            analytics["approved_expenses_by_department"]
        )

        if not expense_df.empty:

            # Keep currencies separate.
            for currency in sorted(
                expense_df["currency_code"].dropna().unique()
            ):

                currency_df = expense_df[
                    expense_df["currency_code"] == currency
                ].copy()

                # Convert paise/cents into currency units.
                currency_df["approved_amount"] = (
                    currency_df["total_amount_minor"] / 100
                )

                total_spend = (
                    currency_df["total_amount_minor"].sum() / 100
                )

                total_claims = int(
                    currency_df["claim_count"].sum()
                )

                st.markdown(f"**{currency} Spending**")

                col1, col2 = st.columns(2)

                with col1:
                    st.metric(
                        f"Total Approved Spend ({currency})",
                        f"{currency} {total_spend:,.2f}"
                    )

                with col2:
                    st.metric(
                        "Approved Claims",
                        total_claims
                    )

                col1, col2 = st.columns(2)

                with col1:
                    st.bar_chart(
                        currency_df.set_index("department")[
                            ["approved_amount"]
                        ]
                    )

                with col2:
                    display_df = currency_df[
                        [
                            "department",
                            "country_code",
                            "claim_count",
                            "approved_amount"
                        ]
                    ].copy()

                    display_df["approved_amount"] = (
                        display_df["approved_amount"].round(2)
                    )

                    st.dataframe(
                        display_df,
                        use_container_width=True,
                        hide_index=True
                    )

        else:
            st.info("No approved expense data available.")

        st.divider()

        # 5. Reimbursement Analytics
        st.subheader("Reimbursement Overview")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Total Reimbursements",
            summary["total_reimbursements"]
        )

        col2.metric(
            "Pending Payment",
            summary["pending_reimbursements"]
        )

        col3.metric(
            "Paid",
            summary["paid_reimbursements"]
        )

        st.divider()

        # 6. Exception Analytics
        st.subheader("Exception Analysis")

        exception_summary = analytics["exception_summary"]

        severity_counts = {
            item["severity"]: item["count"]
            for item in exception_summary["by_severity"]
        }

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Total Findings",
            exception_summary["total_findings"]
        )

        col2.metric(
            "High Severity",
            severity_counts.get("high", 0)
        )

        col3.metric(
            "Medium Severity",
            severity_counts.get("medium", 0)
        )

        exception_type_df = pd.DataFrame(
            exception_summary["by_type"]
        )

        if not exception_type_df.empty:

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Findings by Exception Type**")

                st.bar_chart(
                    exception_type_df.set_index("exception_type")
                )

            with col2:
                st.markdown("**Exception Breakdown**")

                st.dataframe(
                    exception_type_df,
                    use_container_width=True,
                    hide_index=True
                )

        st.divider()

        # 7. Workflow Performance
        st.subheader("Workflow Performance")

        total_leave = summary["total_leave_requests"]
        total_expense = summary["total_expense_claims"]

        leave_rate = (
            summary["approved_leave_requests"] / total_leave * 100
            if total_leave else 0
        )

        expense_rate = (
            summary["approved_expense_claims"] / total_expense * 100
            if total_expense else 0
        )

        col1, col2 = st.columns(2)

        col1.metric(
            "Leave Requests Approved",
            f"{leave_rate:.1f}%"
        )

        col2.metric(
            "Expense Claims Approved",
            f"{expense_rate:.1f}%"
        )

