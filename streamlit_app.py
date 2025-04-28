import streamlit as st
import pandas as pd
import plotly.express as px
import os
import re
import tempfile

st.set_page_config(
    page_title="판매 데이터 분석 대시보드",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 임시 디렉토리 사용
UPLOAD_DIR = tempfile.gettempdir()

def save_uploaded_file(uploaded_file, label):
    if uploaded_file is not None:
        try:
            file_path = os.path.join(UPLOAD_DIR, f"{label}_{uploaded_file.name}")
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            return file_path
        except Exception as e:
            st.error(f"파일 저장 중 오류가 발생했습니다: {str(e)}")
            return None
    return None

@st.cache_data
def load_and_preprocess_from_path(file_path, label):
    if file_path and os.path.exists(file_path):
        try:
            ext = os.path.splitext(file_path)[-1].lower()
            if ext == ".xls":
                df = pd.read_excel(file_path, engine="xlrd")
            elif ext == ".xlsx":
                df = pd.read_excel(file_path, engine="openpyxl")
            elif ext == ".csv":
                df = pd.read_csv(file_path, encoding="utf-8")
            else:
                st.error("지원하지 않는 파일 형식입니다.")
                return None

            # 필수 컬럼 자동 보완
            required_cols = ["분류명", "상품명", "주문수", "실판매금액", "지점명", "월"]
            for col in required_cols:
                if col not in df.columns:
                    if col == "지점명":
                        df[col] = "미지정지점"
                    elif col == "월":
                        df[col] = label
                    else:
                        st.error(f"필수 컬럼이 누락되었습니다: {col}")
                        return None

            # 실판매금액 정제
            def clean_price(x):
                m = re.search(r'\(?([\d,]+)\)?', str(x))
                if m:
                    x = m.group(1)
                x = str(x).replace(',', '')
                try:
                    return float(x)
                except:
                    return 0
            df["실판매금액"] = df["실판매금액"].apply(clean_price)
            
            # 분류그룹 컬럼 생성
            def extract_paren(x):
                m = re.search(r'\(([^)]+)\)', str(x))
                return m.group(1).strip() if m else '기타'
            df["분류그룹"] = df["분류명"].apply(extract_paren)
            
            return df
        except Exception as e:
            st.error(f"데이터 처리 중 오류가 발생했습니다: {str(e)}")
            return None
    return None

st.title("📊 판매 데이터 분석 및 시각화 웹앱")
st.markdown("""
#### 엑셀 파일을 업로드하면 자동으로 판매 데이터를 분석하고, 다양한 차트로 시각화합니다.
- **분류명, 상품명, 주문수, 실판매금액, 지점명, 월** 컬럼이 포함된 엑셀 파일을 업로드하세요.
""")

# 두 파일 업로더 추가
st.markdown("---")
st.header("전달/당월 파일 업로드 및 매출 비교")
uploaded_file1 = st.file_uploader("엑셀/CSV 파일 업로드 (전달)", type=["xlsx", "xls", "csv"], key="file1")
uploaded_file2 = st.file_uploader("엑셀/CSV 파일 업로드 (당월)", type=["xlsx", "xls", "csv"], key="file2")

# 파일 저장 및 세션 상태에 경로 기록
file1_path = save_uploaded_file(uploaded_file1, "전달")
file2_path = save_uploaded_file(uploaded_file2, "당월")
if file1_path:
    st.session_state["file1_path"] = file1_path
if file2_path:
    st.session_state["file2_path"] = file2_path

# 세션에 저장된 파일 경로로 불러오기
df_prev = load_and_preprocess_from_path(st.session_state.get("file1_path"), "전달")
df_curr = load_and_preprocess_from_path(st.session_state.get("file2_path"), "당월")

if df_prev is not None and df_curr is not None:
    st.success("두 파일 모두 업로드 및 처리 완료!")
    # 1. 한눈에 보는 총매출 비교 (중복 제거, 폰트 2배 확대)
    total_prev = df_prev["실판매금액"].sum()
    total_curr = df_curr["실판매금액"].sum()
    total_df = pd.DataFrame({
        "월": ["전달", "당월"],
        "실판매금액": [total_prev, total_curr]
    })
    fig_total = px.bar(
        total_df,
        x="월",
        y="실판매금액",
        text="실판매금액",
        title="전달/당월 총매출 비교",
        labels={"실판매금액": "실판매금액(₩)", "월": "구분"},
        color="월",
        color_discrete_sequence=["#636EFA", "#EF553B"]
    )
    fig_total.update_traces(texttemplate='%{text:,.0f}₩', textposition='outside', marker_line_width=4, textfont_size=20)
    fig_total.update_layout(
        yaxis_tickformat=",",
        yaxis_title_font_size=20,
        xaxis_title_font_size=20,
        title_x=0.5,
        title_font_size=40,
        legend_font_size=24,
        height=800,
        margin=dict(t=60, b=40, l=40, r=40)
    )
    st.plotly_chart(fig_total, use_container_width=True)

    # 2. 실판매금액 상위 10위 분류그룹별 매출 증감 비교 (중복 제거, 폰트 2배 확대)
    st.markdown("#### 실판매금액 상위 10위 분류그룹별 전달/당월 매출 비교", unsafe_allow_html=True)
    group_sum = df_prev.groupby("분류그룹")["실판매금액"].sum() + df_curr.groupby("분류그룹")["실판매금액"].sum()
    top10_groups = group_sum.sort_values(ascending=False).head(10).index.tolist()
    prev_group = df_prev[df_prev["분류그룹"].isin(top10_groups)].groupby("분류그룹")["실판매금액"].sum().reset_index()
    curr_group = df_curr[df_curr["분류그룹"].isin(top10_groups)].groupby("분류그룹")["실판매금액"].sum().reset_index()
    compare = pd.merge(curr_group, prev_group, on="분류그룹", how="outer", suffixes=("_당월", "_전달")).fillna(0)
    compare = compare.sort_values(by="실판매금액_당월", ascending=False)
    fig = px.bar(
        compare,
        x="분류그룹",
        y=["실판매금액_전달", "실판매금액_당월"],
        barmode="group",
        text_auto=True,
        title="실판매금액 상위 10위 분류그룹별 전달/당월 매출 비교",
        labels={"value": "실판매금액(₩)", "분류그룹": "분류그룹", "variable": "구분"},
        color_discrete_sequence=["#636EFA", "#EF553B"]
    )
    fig.update_traces(texttemplate='%{y:,.0f}₩', textposition='outside', textfont_size=88)
    fig.update_layout(
        title_x=0.5,
        title_font_size=25,
        legend_font_size=20,
        xaxis_title_font_size=20,
        yaxis_title_font_size=20,
        yaxis_tickformat=",",
        height=1400,
        margin=dict(t=120, b=80, l=80, r=80)
    )
    st.plotly_chart(fig, use_container_width=True)

    # 3. 실판매금액 상위 10위 분류그룹 증감액 차트 (표 대신 차트)
    compare["증감액"] = compare["실판매금액_당월"] - compare["실판매금액_전달"]
    fig_delta = px.bar(
        compare,
        x="분류그룹",
        y="증감액",
        text="증감액",
        title="실판매금액 상위 10위 분류그룹 증감액",
        labels={"증감액": "증감액(₩)", "분류그룹": "분류그룹"},
        color="증감액",
        color_continuous_scale=["#EF553B", "#636EFA"]
    )
    fig_delta.update_traces(texttemplate='%{text:,.0f}₩', textposition='outside')
    fig_delta.update_layout(
        title_x=0.5,
        title_font_size=28,
        xaxis_title_font_size=18,
        yaxis_title_font_size=18,
        yaxis_tickformat=",",
        height=600,
        margin=dict(t=80, b=40, l=40, r=40)
    )
    st.plotly_chart(fig_delta, use_container_width=True)

    # 4. 주문수 상위 10위 분류그룹별 전달/당월 비교 (막대그래프)
    st.markdown("#### 주문수 상위 10위 분류그룹별 전달/당월 비교")
    # 분류앞 컬럼 생성 (전달/당월 모두)
    def extract_prefix(x):
        import re
        if pd.isna(x) or str(x).strip() == "":
            return "기타"
        m = re.match(r"([^(]+)", str(x))
        return m.group(1).strip() if m else "기타"
    df_prev["분류앞"] = df_prev["분류명"].apply(extract_prefix)
    df_curr["분류앞"] = df_curr["분류명"].apply(extract_prefix)
    # 상위 10위 분류앞 추출 (주문수 합산 기준)
    order_sum = df_prev.groupby("분류앞")["주문수"].sum() + df_curr.groupby("분류앞")["주문수"].sum()
    top10_order_groups = order_sum.sort_values(ascending=False).head(10).index.tolist()
    prev_order = df_prev[df_prev["분류앞"].isin(top10_order_groups)].groupby("분류앞")["주문수"].sum().reset_index()
    curr_order = df_curr[df_curr["분류앞"].isin(top10_order_groups)].groupby("분류앞")["주문수"].sum().reset_index()
    order_compare = pd.merge(curr_order, prev_order, on="분류앞", how="outer", suffixes=("_당월", "_전달")).fillna(0)
    order_compare = order_compare.sort_values(by="주문수_당월", ascending=False)
    fig_order = px.bar(
        order_compare,
        x="분류앞",
        y=["주문수_전달", "주문수_당월"],
        barmode="group",
        text_auto=True,
        title="주문수 상위 10위 분류그룹별 전달/당월 비교",
        labels={"value": "주문수", "분류앞": "분류그룹", "variable": "구분"},
        color_discrete_sequence=["#636EFA", "#EF553B"]
    )
    fig_order.update_traces(texttemplate='%{y:,.0f}', textposition='outside')
    fig_order.update_layout(
        title_x=0.5,
        title_font_size=32,
        legend_font_size=20,
        xaxis_title_font_size=20,
        yaxis_title_font_size=20,
        yaxis_tickformat=",",
        height=800,
        margin=dict(t=100, b=80, l=80, r=80)
    )
    st.plotly_chart(fig_order, use_container_width=True)

    # 보고서 expander 버튼 및 내용 (한 번만 표시)
    if 'show_report' not in st.session_state:
        st.session_state['show_report'] = False
    st.markdown('<div style="margin-bottom: 1em;"><button style="font-size:1.2em;padding:0.5em 1.5em;" onclick="window.dispatchEvent(new Event(\'report_click\'))">보고서 보기</button></div>', unsafe_allow_html=True)
    if st.button('보고서 보기', key='report_btn'):
        st.session_state['show_report'] = not st.session_state['show_report']
    with st.expander('전월/당월 매출 분석 요약 보고서', expanded=st.session_state['show_report']):
        # 전체 매출 동향
        total_prev = df_prev["실판매금액"].sum()
        total_curr = df_curr["실판매금액"].sum()
        diff = total_curr - total_prev
        diff_rate = (diff / total_prev * 100) if total_prev else 0
        st.markdown(f"<span style='font-size:1.5em;font-weight:bold;'>1. 전체 매출 동향</span>", unsafe_allow_html=True)
        st.markdown(f"<span style='font-size:1.3em;'>- 전달 총매출: {total_prev:,.0f}원</span>", unsafe_allow_html=True)
        st.markdown(f"<span style='font-size:1.3em;'>- 당월 총매출: {total_curr:,.0f}원</span>", unsafe_allow_html=True)
        st.markdown(f"<span style='font-size:1.3em;'>- 매출 증감: {diff:+,.0f}원 ({diff_rate:+.1f}%)</span>", unsafe_allow_html=True)
        st.markdown(f"<span style='font-size:1.3em;'>> 당월 전체 매출이 전달 대비 {abs(diff_rate):.1f}% {'증가' if diff > 0 else '감소'}하였습니다.</span>", unsafe_allow_html=True)

        # 실판매금액 상위/하위 3위 분류그룹별 변화
        group_sum = df_prev.groupby("분류그룹")["실판매금액"].sum() + df_curr.groupby("분류그룹")["실판매금액"].sum()
        top10_groups = group_sum.sort_values(ascending=False).head(10).index.tolist()
        prev_group = df_prev[df_prev["분류그룹"].isin(top10_groups)].groupby("분류그룹")["실판매금액"].sum().reset_index()
        curr_group = df_curr[df_curr["분류그룹"].isin(top10_groups)].groupby("분류그룹")["실판매금액"].sum().reset_index()
        compare = pd.merge(curr_group, prev_group, on="분류그룹", how="outer", suffixes=("_당월", "_전달")).fillna(0)
        compare["증감액"] = compare["실판매금액_당월"] - compare["실판매금액_전달"]
        compare["증감률"] = (compare["증감액"] / compare["실판매금액_전달"].replace(0, 1)) * 100
        st.markdown(f"<span style='font-size:1.5em;font-weight:bold;'>2. 실판매금액 변화 상위/하위 분류</span>", unsafe_allow_html=True)
        top3 = compare.sort_values(by='증감액', ascending=False).head(3)
        bottom3 = compare.sort_values(by='증감액').head(3)
        for idx, row in top3.iterrows():
            st.markdown(f"<span style='font-size:1.3em;'>▲ <b>{row['분류그룹']}</b>: 전달 {row['실판매금액_전달']:,.0f}원 → 당월 {row['실판매금액_당월']:,.0f}원 (증감: +{row['증감액']:,.0f}원, {row['증감률']:+.1f}%)</span>", unsafe_allow_html=True)
        for idx, row in bottom3.iterrows():
            st.markdown(f"<span style='font-size:1.3em;'>▼ <b>{row['분류그룹']}</b>: 전달 {row['실판매금액_전달']:,.0f}원 → 당월 {row['실판매금액_당월']:,.0f}원 (증감: {row['증감액']:,.0f}원, {row['증감률']:+.1f}%)</span>", unsafe_allow_html=True)

        # 주문수 상위/하위 3위 분류그룹별 변화
        def extract_prefix(x):
            import re
            if pd.isna(x) or str(x).strip() == "":
                return "기타"
            m = re.match(r"([^(]+)", str(x))
            return m.group(1).strip() if m else "기타"
        df_prev["분류앞"] = df_prev["분류명"].apply(extract_prefix)
        df_curr["분류앞"] = df_curr["분류명"].apply(extract_prefix)
        order_sum = df_prev.groupby("분류앞")["주문수"].sum() + df_curr.groupby("분류앞")["주문수"].sum()
        top10_order_groups = order_sum.sort_values(ascending=False).head(10).index.tolist()
        prev_order = df_prev[df_prev["분류앞"].isin(top10_order_groups)].groupby("분류앞")["주문수"].sum().reset_index()
        curr_order = df_curr[df_curr["분류앞"].isin(top10_order_groups)].groupby("분류앞")["주문수"].sum().reset_index()
        order_compare = pd.merge(curr_order, prev_order, on="분류앞", how="outer", suffixes=("_당월", "_전달")).fillna(0)
        order_compare["증감"] = order_compare["주문수_당월"] - order_compare["주문수_전달"]
        order_compare["증감률"] = (order_compare["증감"] / order_compare["주문수_전달"].replace(0, 1)) * 100
        st.markdown(f"<span style='font-size:1.5em;font-weight:bold;'>3. 주문수 변화 상위/하위 분류</span>", unsafe_allow_html=True)
        top3_order = order_compare.sort_values(by='증감', ascending=False).head(3)
        bottom3_order = order_compare.sort_values(by='증감').head(3)
        for idx, row in top3_order.iterrows():
            st.markdown(f"<span style='font-size:1.3em;'>▲ <b>{row['분류앞']}</b>: 전달 {row['주문수_전달']:,}건 → 당월 {row['주문수_당월']:,}건 (증감: +{row['증감']:,}건, {row['증감률']:+.1f}%)</span>", unsafe_allow_html=True)
        for idx, row in bottom3_order.iterrows():
            st.markdown(f"<span style='font-size:1.3em;'>▼ <b>{row['분류앞']}</b>: 전달 {row['주문수_전달']:,}건 → 당월 {row['주문수_당월']:,}건 (증감: {row['증감']:,}건, {row['증감률']:+.1f}%)</span>", unsafe_allow_html=True)

    # 실판매금액 컬럼에서 괄호, 콤마 등 제거 후 숫자로 변환
    def clean_price(x):
        import re
        m = re.search(r'\(?([\d,]+)\)?', str(x))
        if m:
            x = m.group(1)
        x = str(x).replace(',', '')
        try:
            return float(x)
        except:
            return 0
    df_prev["실판매금액"] = df_prev["실판매금액"].apply(clean_price)
    df_curr["실판매금액"] = df_curr["실판매금액"].apply(clean_price)

    # 분류그룹(괄호 안 단어) 컬럼 생성
    def extract_paren(x):
        m = re.search(r'\(([^)]+)\)', str(x))
        return m.group(1).strip() if m else '기타'
    df_prev["분류그룹"] = df_prev["분류명"].apply(extract_paren)
    df_curr["분류그룹"] = df_curr["분류명"].apply(extract_paren)

    # 차트 제목 변수로 분리 및 가운데 정렬
    sales_title = "실판매금액 상위 10위"
    sales_chart_title = "실판매금액 상위 10위"
    count_title = "판매건수 상위 10"
    count_chart_title = "판매건수 상위 10위"
    order_title = "주문수 상위 10개 원형차트"
    order_chart_title = "주문수(분류) 상위 10위"

    # 실판매금액 기준 분류그룹(괄호 안 단어) 상위 10개 원형차트 (더 크게, 글씨 더 크게, 가운데 정렬)
    st.markdown("---")
    group_sales = df_prev.groupby("분류그룹")["실판매금액"].sum().sort_values(ascending=False).head(10).reset_index()
    group_sales.columns = ["분류그룹", "실판매금액"]
    fig_cat_sales = px.pie(group_sales, names="분류그룹", values="실판매금액", title=sales_chart_title)
    fig_cat_sales.update_traces(
        textinfo='label+percent',
        textposition='inside',
        textfont_size=44,
        pull=[0.09]*len(group_sales),
        marker=dict(line=dict(color='#000000', width=6))
    )
    fig_cat_sales.update_layout(
        height=1600,
        legend_font_size=48,
        legend_title_font_size=54,
        title_font_size=64,
        title_x=0.5,
        margin=dict(t=120, b=80, l=80, r=80)
    )
    st.plotly_chart(fig_cat_sales, use_container_width=True)

    # 기타 그룹 상세 보기 버튼 및 차트/표 표시
    if "기타" in group_sales["분류그룹"].values:
        if st.button("기타 상세 보기"):
            etc_data = df_prev[df_prev["분류그룹"] == "기타"]
            st.markdown("### 기타 그룹 상세 데이터 (실판매금액 상위 10 상품)")
            top_etc = etc_data.groupby("상품명")["실판매금액"].sum().sort_values(ascending=False).head(10).reset_index()
            st.bar_chart(top_etc.set_index("상품명"))
            st.dataframe(etc_data)

    # 분류명에서 괄호 앞 단어로 그룹화 (예: '(어뉴)' 등), 건수 기준 상위 10개 원형차트 (크기/글씨/정렬 통일)
    st.markdown("---")
    top10_paren = df_prev["분류그룹"].value_counts().head(10).reset_index()
    top10_paren.columns = ["분류그룹", "건수"]
    fig_cat = px.pie(top10_paren, names="분류그룹", values="건수", title=count_chart_title)
    fig_cat.update_traces(
        textinfo='label+percent',
        textposition='inside',
        textfont_size=44,
        pull=[0.09]*len(top10_paren),
        marker=dict(line=dict(color='#000000', width=6))
    )
    fig_cat.update_layout(
        height=1600,
        legend_font_size=48,
        legend_title_font_size=54,
        title_font_size=64,
        title_x=0.5,
        margin=dict(t=120, b=80, l=80, r=80)
    )
    st.plotly_chart(fig_cat, use_container_width=True)

    # 주문수 상위 10개 원형차트 (분류명 괄호 앞 단어 기준 그룹화)
    st.markdown("---")
    def extract_prefix(x):
        import re
        if pd.isna(x) or str(x).strip() == "":
            return "기타"
        m = re.match(r"([^(]+)", str(x))
        return m.group(1).strip() if m else "기타"
    df_prev["분류앞"] = df_prev["분류명"].apply(extract_prefix)
    top10_order_group = df_prev.groupby("분류앞")["주문수"].sum().sort_values(ascending=False).head(10).reset_index()
    fig_order = px.pie(top10_order_group, names="분류앞", values="주문수", title=order_chart_title)
    fig_order.update_traces(
        textinfo='label+percent',
        textposition='inside',
        textfont_size=44,
        pull=[0.09]*len(top10_order_group),
        marker=dict(line=dict(color='#000000', width=6))
    )
    fig_order.update_layout(
        height=1600,
        legend_font_size=48,
        legend_title_font_size=54,
        title_font_size=64,
        title_x=0.5,
        margin=dict(t=120, b=80, l=80, r=80)
    )
    st.plotly_chart(fig_order, use_container_width=True)

    # 4. 특이사항 및 제언
    top_categories = df_curr.groupby("분류그룹")["실판매금액"].agg(['sum', 'count']).reset_index()
    top_categories.columns = ['카테고리', '매출액', '주문건수']
    top_categories = top_categories.sort_values('매출액', ascending=False).head(5)
    
    # 상위 5개 카테고리 매출 비중
    total_top5_sales = top_categories['매출액'].sum()
    sales_ratio = (total_top5_sales / total_curr) * 100
    
    top5_list = [f"{row['카테고리']} ({row['매출액']:,.0f}원, {(row['매출액']/total_curr*100):.1f}%)" 
                 for idx, row in top_categories.iterrows()]
    top5_str = '\n        - '.join(top5_list)
    
    st.markdown(f"""
    <h2 style='font-size: 30px;'>4. 특이사항 및 제언</h2>
    <div style='font-size: 23px;'>
    1. <strong>매출 집중도</strong>
        - 상위 5개 카테고리가 전체 매출의 {sales_ratio:.1f}%를 차지하고 있어, 이들 카테고리에 대한 재고관리가 중요합니다.
        - <strong>상위 5개 카테고리 상세:</strong>
        - {top5_str}
        
    2. <strong>판매 전략 제안</strong>
        - 높은 객단가 카테고리의 프로모션을 통한 매출 증대 가능성이 있습니다.
        - 주문건수가 많은 카테고리의 경우, 번들상품 구성을 통한 객단가 상승을 고려해볼 수 있습니다.
    
    3. <strong>재고 및 운영 관련</strong>
        - 상위 매출 카테고리의 안정적인 재고 확보가 필요합니다.
        - 높은 회전율을 보이는 상품들의 공급망 관리에 집중이 필요합니다.
    </div>
    """, unsafe_allow_html=True)

elif df_curr is not None:
    st.success("당월 파일만 업로드됨: 단일 파일 분석 차트 표시")
    
    # 상세 보고서 섹션 추가
    st.markdown("<h1 style='font-size: 35px;'>📊 당월 판매 실적 분석 보고서</h1>", unsafe_allow_html=True)
    
    # 1. 전체 매출 현황
    total_sales = df_curr["실판매금액"].sum()
    total_orders = df_curr["주문수"].sum()
    avg_order_value = total_sales / total_orders if total_orders > 0 else 0
    
    st.markdown(f"""
    <h2 style='font-size: 30px;'>1. 전체 매출 현황</h2>
    <div style='font-size: 23px;'>
    - **총 매출액**: {total_sales:,.0f}원
    - **총 주문 건수**: {total_orders:,.0f}건
    - **평균 주문 금액**: {avg_order_value:,.0f}원
    </div>
    """, unsafe_allow_html=True)
    
    # 2. 상위 매출 카테고리 분석
    st.markdown("<h2 style='font-size: 30px;'>2. 상위 매출 카테고리 분석</h2>", unsafe_allow_html=True)
    top_categories = df_curr.groupby("분류그룹")["실판매금액"].agg(['sum', 'count']).reset_index()
    top_categories.columns = ['카테고리', '매출액', '주문건수']
    top_categories = top_categories.sort_values('매출액', ascending=False).head(5)
    
    # 상위 5개 카테고리 매출 비중
    total_top5_sales = top_categories['매출액'].sum()
    sales_ratio = (total_top5_sales / total_sales) * 100
    
    st.markdown(f"""
    <h3 style='font-size: 25px;'>상위 5개 카테고리 (매출액 기준)</h3>
    <div style='font-size: 23px;'>
    - 상위 5개 카테고리 총 매출: {total_top5_sales:,.0f}원 (전체 매출의 {sales_ratio:.1f}%)
    </div>
    """, unsafe_allow_html=True)
    
    for idx, row in top_categories.iterrows():
        category_ratio = (row['매출액'] / total_sales) * 100
        st.markdown(f"""
        <div style='font-size: 23px;'>
        <strong>{row['카테고리']}</strong>
        - 매출액: {row['매출액']:,.0f}원 (전체의 {category_ratio:.1f}%)
        - 주문건수: {row['주문건수']:,.0f}건
        </div>
        """, unsafe_allow_html=True)
    
    # 3. 주문 분석
    st.markdown("<h2 style='font-size: 30px;'>3. 주문 패턴 분석</h2>", unsafe_allow_html=True)
    avg_order_by_category = df_curr.groupby("분류그룹")["실판매금액"].mean().sort_values(ascending=False).head(3)
    
    st.markdown("""
    <h3 style='font-size: 25px;'>높은 객단가 카테고리 (평균 주문금액 기준)</h3>
    """, unsafe_allow_html=True)
    
    for cat, avg in avg_order_by_category.items():
        st.markdown(f"""
        <div style='font-size: 23px;'>
        - <strong>{cat}</strong>: {avg:,.0f}원
        </div>
        """, unsafe_allow_html=True)
    
    # 4. 특이사항 및 제언
    top5_list = [f"{row['카테고리']} ({row['매출액']:,.0f}원, {(row['매출액']/total_sales*100):.1f}%)" 
                 for idx, row in top_categories.iterrows()]
    top5_str = '\n        - '.join(top5_list)
    
    st.markdown(f"""
    <h2 style='font-size: 30px;'>4. 특이사항 및 제언</h2>
    <div style='font-size: 23px;'>
    1. <strong>매출 집중도</strong>
        - 상위 5개 카테고리가 전체 매출의 {sales_ratio:.1f}%를 차지하고 있어, 이들 카테고리에 대한 재고관리가 중요합니다.
        - <strong>상위 5개 카테고리 상세:</strong>
        - {top5_str}
        
    2. <strong>판매 전략 제안</strong>
        - 높은 객단가 카테고리의 프로모션을 통한 매출 증대 가능성이 있습니다.
        - 주문건수가 많은 카테고리의 경우, 번들상품 구성을 통한 객단가 상승을 고려해볼 수 있습니다.
    
    3. <strong>재고 및 운영 관련</strong>
        - 상위 매출 카테고리의 안정적인 재고 확보가 필요합니다.
        - 높은 회전율을 보이는 상품들의 공급망 관리에 집중이 필요합니다.
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 기존의 차트 표시 코드
    # 실판매금액 기준 분류그룹(괄호 안 단어) 상위 10개 원형차트
    group_sales = df_curr.groupby("분류그룹")["실판매금액"].sum().sort_values(ascending=False).head(10).reset_index()
    group_sales.columns = ["분류그룹", "실판매금액"]
    fig_cat_sales = px.pie(group_sales, names="분류그룹", values="실판매금액", title="당월 실판매금액 상위 10위")
    fig_cat_sales.update_traces(
        textinfo='label+percent',
        textposition='inside',
        textfont_size=44,
        pull=[0.09]*len(group_sales),
        marker=dict(line=dict(color='#000000', width=6))
    )
    fig_cat_sales.update_layout(
        height=1600,
        legend_font_size=48,
        legend_title_font_size=54,
        title_font_size=64,
        title_x=0.5,
        margin=dict(t=120, b=80, l=80, r=80)
    )
    st.plotly_chart(fig_cat_sales, use_container_width=True)

    # 기타 그룹 상세 보기 버튼 및 차트/표 표시
    if "기타" in group_sales["분류그룹"].values:
        if st.button("기타 상세 보기"):
            etc_data = df_curr[df_curr["분류그룹"] == "기타"]
            st.markdown("### 기타 그룹 상세 데이터 (당월 실판매금액 상위 10 상품)")
            top_etc = etc_data.groupby("상품명")["실판매금액"].sum().sort_values(ascending=False).head(10).reset_index()
            st.bar_chart(top_etc.set_index("상품명"))
            st.dataframe(etc_data)

    # 분류명에서 괄호 앞 단어로 그룹화, 건수 기준 상위 10개 원형차트
    st.markdown("---")
    top10_paren = df_curr["분류그룹"].value_counts().head(10).reset_index()
    top10_paren.columns = ["분류그룹", "건수"]
    fig_cat = px.pie(top10_paren, names="분류그룹", values="건수", title="당월 판매건수 상위 10위")
    fig_cat.update_traces(
        textinfo='label+percent',
        textposition='inside',
        textfont_size=44,
        pull=[0.09]*len(top10_paren),
        marker=dict(line=dict(color='#000000', width=6))
    )
    fig_cat.update_layout(
        height=1600,
        legend_font_size=48,
        legend_title_font_size=54,
        title_font_size=64,
        title_x=0.5,
        margin=dict(t=120, b=80, l=80, r=80)
    )
    st.plotly_chart(fig_cat, use_container_width=True)

    # 주문수 상위 10개 원형차트 (분류명 괄호 앞 단어 기준 그룹화)
    st.markdown("---")
    def extract_prefix(x):
        import re
        if pd.isna(x) or str(x).strip() == "":
            return "기타"
        m = re.match(r"([^(]+)", str(x))
        return m.group(1).strip() if m else "기타"
    df_curr["분류앞"] = df_curr["분류명"].apply(extract_prefix)
    top10_order_group = df_curr.groupby("분류앞")["주문수"].sum().sort_values(ascending=False).head(10).reset_index()
    fig_order = px.pie(top10_order_group, names="분류앞", values="주문수", title="당월 주문수(분류) 상위 10위")
    fig_order.update_traces(
        textinfo='label+percent',
        textposition='inside',
        textfont_size=44,
        pull=[0.09]*len(top10_order_group),
        marker=dict(line=dict(color='#000000', width=6))
    )
    fig_order.update_layout(
        height=1600,
        legend_font_size=48,
        legend_title_font_size=54,
        title_font_size=64,
        title_x=0.5,
        margin=dict(t=120, b=80, l=80, r=80)
    )
    st.plotly_chart(fig_order, use_container_width=True)