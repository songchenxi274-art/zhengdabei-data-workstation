from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from research_desk.ai import GuidanceService, ProviderRegistry, ProviderStatus
from research_desk.audit import AuditLogger
from research_desk.analysis import (
    QUARTILE_ALGORITHM,
    calculate_correlation,
    calculate_reliability,
    categorical_frequencies,
    create_static_scatter_svg,
    numeric_descriptives,
    ordinal_descriptives,
)
from research_desk.csv_export import UnsafeCsvValueError, dataframe_to_safe_csv
from research_desk.data_io import (
    DataConfigurationError,
    assess_quality,
    list_excel_sheets,
    load_csv,
    load_xlsx,
    prepare_analysis_frame,
)
from research_desk.models import (
    SamplingDesign,
    VARIABLE_TYPE_LABELS,
    VariableType,
    infer_schema,
)
from research_desk.storage import ProjectStore, default_workspace_dir
from research_desk.security import (
    AuthorizationError,
    DataLevel,
    DisclosureTracker,
    OnlineRequestPayload,
    build_authorized_request,
    evaluate_online_boundary,
    verify_authorized_payload,
)


st.set_page_config(
    page_title="Research Desk",
    page_icon="RD",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_store() -> tuple[ProjectStore, Path]:
    workspace = default_workspace_dir()
    store = ProjectStore(workspace / "research_desk.sqlite3")
    store.initialize()
    return store, workspace


def initialize_state() -> None:
    defaults = {
        "frame": None,
        "analysis_frame": None,
        "source_name": None,
        "schema": {},
        "conversion_report": pd.DataFrame(),
        "column_changes": (),
        "sampling_design": SamplingDesign.UNDECLARED,
        "correlation_result": None,
        "reliability_result": None,
        "project_id": None,
        "pending_project_id": None,
        "data_version": 0,
        "project_delete_error": None,
        "disclosure_tracker": DisclosureTracker(),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def analysis_numeric_fields(schema: dict[str, VariableType]) -> list[str]:
    return [
        field
        for field, variable_type in schema.items()
        if variable_type in {VariableType.NUMERIC, VariableType.ORDINAL}
    ]


def error_summary(context: str, error: Exception) -> str:
    return f"{context}（{type(error).__name__}）"


def clear_correlation_result() -> None:
    st.session_state["correlation_result"] = None


def clear_reliability_result() -> None:
    st.session_state["reliability_result"] = None


def clear_all_results() -> None:
    clear_correlation_result()
    clear_reliability_result()


def reset_session_data() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(
            (
                "type_",
                "missing_codes_",
                "correlation_",
                "reliability_",
                "export_",
                "sampling_",
            )
        ):
            del st.session_state[key]
    st.session_state["frame"] = None
    st.session_state["analysis_frame"] = None
    st.session_state["source_name"] = None
    st.session_state["schema"] = {}
    st.session_state["conversion_report"] = pd.DataFrame()
    st.session_state["column_changes"] = ()
    st.session_state["sampling_design"] = SamplingDesign.UNDECLARED
    st.session_state["correlation_result"] = None
    st.session_state["reliability_result"] = None


def current_project(store: ProjectStore):
    project_id = st.session_state.get("project_id")
    if project_id is None:
        return None
    try:
        return store.get_project(int(project_id))
    except KeyError:
        st.session_state["project_id"] = None
        return None


def save_result(store: ProjectStore, analysis_type: str, parameters: dict, result: dict) -> None:
    if store is None:
        st.warning("SQLite 不可用，当前结果仅保存在临时会话中。")
        return
    project = current_project(store)
    if project is None:
        st.warning("请先在侧边栏创建或选择项目，再保存分析结果。")
        return
    try:
        store.save_analysis(project.id, analysis_type, parameters, result)
        st.success(f"结果已保存到项目“{project.name}”。")
    except (OSError, sqlite3.Error) as exc:
        st.error(error_summary("保存失败", exc))


def delete_project_callback(store: ProjectStore) -> None:
    project_id = st.session_state.get("project_id")
    if project_id is None:
        return
    try:
        store.clear_project(int(project_id))
    except (OSError, sqlite3.Error) as exc:
        st.session_state["project_delete_error"] = error_summary("项目删除失败", exc)
        return
    st.session_state["project_delete_error"] = None
    st.session_state["project_id"] = None
    st.session_state["project_selector"] = None


initialize_state()

try:
    store, workspace = get_store()
    audit = AuditLogger(workspace / "audit.jsonl")
    database_error = None
except (OSError, sqlite3.Error) as exc:
    store = None
    workspace = default_workspace_dir()
    audit = AuditLogger(workspace / "audit.jsonl")
    database_error = error_summary("SQLite 初始化失败", exc)

st.title("Research Desk")
st.caption("本地优先的问卷数据分析工作台")

with st.sidebar:
    st.subheader("项目")
    if store is None:
        st.error("SQLite 项目存储不可用，当前仅可进行临时会话。")
        if database_error:
            st.caption(database_error)
    else:
        try:
            projects = store.list_projects()
        except (OSError, sqlite3.Error) as exc:
            projects = []
            st.error(error_summary("项目列表读取失败", exc))
        projects_by_id = {project.id: project for project in projects}
        project_options = [None, *projects_by_id]
        if st.session_state["pending_project_id"] is not None:
            st.session_state["project_selector"] = st.session_state["pending_project_id"]
            st.session_state["pending_project_id"] = None
        selected_project = st.selectbox(
            "当前项目",
            options=project_options,
            index=0,
            format_func=lambda project_id: (
                "未选择项目" if project_id is None else projects_by_id[project_id].name
            ),
            key="project_selector",
        )
        st.session_state["project_id"] = selected_project

        with st.form("create_project_form", clear_on_submit=True):
            project_name = st.text_input("新项目名称", max_chars=80)
            create_project = st.form_submit_button(
                "创建项目",
                icon=":material/create_new_folder:",
                width="stretch",
            )
        if create_project:
            if not project_name.strip():
                st.warning("项目名称不能为空。")
            else:
                try:
                    project = store.create_project(project_name)
                    st.session_state["project_id"] = project.id
                    st.session_state["pending_project_id"] = project.id
                    st.success(f"已创建项目“{project.name}”。")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.warning("项目名称已存在。")
                except (OSError, sqlite3.Error) as exc:
                    st.error(error_summary("创建项目失败", exc))

        selected_project_record = projects_by_id.get(st.session_state["project_id"])
        if selected_project_record is not None:
            try:
                backup_data = store.backup_bytes()
                st.download_button(
                    "下载数据库备份",
                    data=backup_data,
                    file_name="research_desk_backup.sqlite3",
                    mime="application/vnd.sqlite3",
                    icon=":material/backup:",
                    width="stretch",
                )
            except (OSError, sqlite3.Error) as exc:
                st.error(error_summary("数据库备份失败", exc))

            confirm_delete = st.checkbox(
                "确认删除当前项目及其分析记录",
                key="confirm_delete_project",
            )
            st.button(
                "删除当前项目",
                icon=":material/delete_forever:",
                type="secondary",
                disabled=not confirm_delete,
                on_click=delete_project_callback,
                args=(store,),
                width="stretch",
            )
            if st.session_state.get("project_delete_error"):
                st.error(st.session_state["project_delete_error"])

    st.divider()
    st.subheader("导入数据")
    uploaded = st.file_uploader("选择 CSV 或 XLSX 文件", type=["csv", "xlsx"])
    if uploaded is not None:
        raw = uploaded.getvalue()
        suffix = Path(uploaded.name).suffix.lower()
        if suffix == ".csv":
            encoding = st.selectbox("文本编码", ["utf-8-sig", "utf-8", "gb18030"])
            delimiter_label = st.selectbox(
                "字段分隔符",
                ["自动识别", "逗号", "制表符", "分号", "竖线"],
            )
            delimiter = {
                "自动识别": None,
                "逗号": ",",
                "制表符": "\t",
                "分号": ";",
                "竖线": "|",
            }[delimiter_label]
            sheet_name = None
        else:
            try:
                sheets = list_excel_sheets(raw)
                sheet_name = st.selectbox("工作表", sheets) if sheets else None
            except Exception as exc:
                st.error(error_summary("无法读取工作表", exc))
                sheet_name = None
            encoding = None
            delimiter = None

        if st.button(
            "载入数据",
            icon=":material/upload_file:",
            width="stretch",
            disabled=sheet_name is None and suffix == ".xlsx",
        ):
            try:
                if suffix == ".csv":
                    loaded = load_csv(raw, uploaded.name, encoding or "utf-8-sig", delimiter)
                else:
                    loaded = load_xlsx(raw, uploaded.name, sheet_name or "")
                prepared = prepare_analysis_frame(
                    loaded.frame,
                    infer_schema(loaded.frame),
                )
                st.session_state["frame"] = loaded.frame
                st.session_state["analysis_frame"] = prepared.frame
                st.session_state["source_name"] = loaded.source_name
                st.session_state["schema"] = infer_schema(loaded.frame)
                st.session_state["conversion_report"] = prepared.conversion_report
                st.session_state["column_changes"] = loaded.column_changes
                st.session_state["data_version"] += 1
                st.session_state["sampling_design"] = SamplingDesign.UNDECLARED
                st.session_state["sampling_selector"] = "请选择"
                st.session_state["correlation_result"] = None
                st.session_state["reliability_result"] = None
                audit.record("data_import", outcome="success")
                st.success(f"已载入 {len(loaded.frame):,} 行、{len(loaded.frame.columns)} 列。")
                if loaded.column_changes:
                    st.warning(
                        "部分字段名已规范化以避免重复："
                        + "；".join(f"{old} → {new}" for old, new in loaded.column_changes)
                    )
            except Exception as exc:
                st.error(error_summary("数据载入失败", exc))

    if st.session_state["frame"] is not None:
        st.divider()
        st.subheader("抽样设计")
        sampling_options = {
            "请选择": SamplingDesign.UNDECLARED,
            "普通未加权独立观测": SamplingDesign.ORDINARY,
            "复杂抽样": SamplingDesign.COMPLEX,
            "不确定": SamplingDesign.UNCERTAIN,
        }
        selected_sampling_label = st.selectbox(
            "数据生成方式",
            list(sampling_options),
            index=0,
            help="该声明决定是否允许正式统计推断。",
            key="sampling_selector",
            on_change=clear_all_results,
        )
        st.session_state["sampling_design"] = sampling_options[selected_sampling_label]
        sampling_design = st.session_state["sampling_design"]
        if sampling_design is SamplingDesign.ORDINARY:
            st.success("普通未加权独立观测：允许按界面条件评估推断结果。")
        elif sampling_design is SamplingDesign.UNDECLARED:
            st.warning("尚未声明抽样设计，正式推断暂不可用。")
        else:
            st.warning("复杂或不确定设计：仅提供描述结果，正式总体推断已禁用。")

        st.button(
            "清除当前会话数据",
            icon=":material/delete_sweep:",
            on_click=reset_session_data,
        )

raw_frame: pd.DataFrame | None = st.session_state["frame"]
if raw_frame is None:
    st.info("从侧边栏导入 CSV 或 XLSX 文件后开始分析。")
    st.stop()

schema: dict[str, VariableType] = st.session_state["schema"]
analysis_frame: pd.DataFrame = (
    st.session_state["analysis_frame"]
    if st.session_state["analysis_frame"] is not None
    else raw_frame
)
sampling_design: SamplingDesign = st.session_state["sampling_design"]

with st.expander("字段类型", expanded=False):
    st.caption("类型和缺失代码只用于派生分析数据，不修改原始表。")
    labels = list(VARIABLE_TYPE_LABELS.values())
    with st.form("field_config_form"):
        new_schema = {}
        missing_code_inputs = {}
        for column in raw_frame.columns:
            current_type = schema.get(str(column), VariableType.UNKNOWN)
            current_label = VARIABLE_TYPE_LABELS[current_type]
            selected_label = st.selectbox(
                str(column),
                labels,
                index=labels.index(current_label),
                key=f"type_{st.session_state['data_version']}_{column}",
            )
            new_schema[str(column)] = next(
                variable_type
                for variable_type, label in VARIABLE_TYPE_LABELS.items()
                if label == selected_label
            )
            missing_key = f"missing_codes_{st.session_state['data_version']}_{column}"
            st.session_state.setdefault(missing_key, "")
            missing_code_inputs[str(column)] = st.text_input(
                f"{column} 的缺失代码",
                help="逗号分隔；仅在提交字段配置时应用。",
                key=missing_key,
            )
        allow_invalid = st.checkbox(
            "我确认将无法转换的值标记为缺失",
            value=False,
        )
        apply_config = st.form_submit_button(
            "应用字段配置",
            icon=":material/tune:",
            width="stretch",
        )

    if apply_config:
        missing_codes = {
            field: value.split(",")
            for field, value in missing_code_inputs.items()
            if value.strip()
        }
        try:
            prepared = prepare_analysis_frame(
                raw_frame,
                new_schema,
                missing_codes,
                allow_invalid_as_missing=allow_invalid,
            )
        except DataConfigurationError as exc:
            st.error(str(exc))
            st.dataframe(
                exc.conversion_report,
                width="stretch",
                alt="字段类型转换失败统计",
            )
        else:
            st.session_state["schema"] = new_schema
            st.session_state["analysis_frame"] = prepared.frame
            st.session_state["conversion_report"] = prepared.conversion_report
            schema = new_schema
            analysis_frame = prepared.frame
            clear_all_results()
            st.success("字段配置已应用。")

    conversion_report = st.session_state["conversion_report"]
    if isinstance(conversion_report, pd.DataFrame) and not conversion_report.empty:
        st.caption("字段类型转换报告")
        st.dataframe(
            conversion_report,
            width="stretch",
            alt="字段类型转换结果",
        )

quality = assess_quality(raw_frame)
analysis_quality = assess_quality(analysis_frame)
metric_columns = st.columns(4)
metric_columns[0].metric("行", f"{quality.rows:,}")
metric_columns[1].metric("列", f"{quality.columns:,}")
metric_columns[2].metric("重复行", f"{quality.duplicate_rows:,}")
metric_columns[3].metric("常量字段", f"{len(quality.constant_fields):,}")

if sampling_design.allows_inference:
    st.success("抽样声明：普通未加权独立观测。推断仍受样本代表性和方法假设限制。")
else:
    st.warning(f"抽样声明：{sampling_design.label}。当前结果仅作未加权描述。")

tabs = st.tabs(["数据概览", "描述统计", "相关分析", "信度分析", "导出", "AI 引导"])

with tabs[0]:
    st.subheader("数据预览")
    st.dataframe(
        raw_frame.head(200),
        width="stretch",
        alt="原始数据前 200 行预览",
    )
    st.caption("仅显示前 200 行预览。")

    st.subheader("数据质量")
    missing_comparison = quality.missing_by_field.merge(
        analysis_quality.missing_by_field,
        on="字段",
        suffixes=("（原始）", "（分析）"),
    )
    st.dataframe(
        missing_comparison.assign(
            缺失比例原始=lambda item: item["缺失比例（原始）"].map(lambda value: f"{value:.1%}"),
            缺失比例分析=lambda item: item["缺失比例（分析）"].map(lambda value: f"{value:.1%}"),
        ).drop(columns=["缺失比例（原始）", "缺失比例（分析）"]),
        width="stretch",
        alt="原始数据与派生分析数据的缺失值对照",
    )
    if quality.constant_fields:
        st.warning(f"常量字段：{', '.join(quality.constant_fields)}")

    if st.button("保存数据概览到项目", icon=":material/save:"):
        save_result(
            store,
            "data_quality",
            {"source_name": st.session_state["source_name"], "sampling_design": sampling_design.value},
            {
                "rows": quality.rows,
                "columns": quality.columns,
                "duplicate_rows": quality.duplicate_rows,
                "constant_fields": list(quality.constant_fields),
            },
        )

with tabs[1]:
    numeric_fields = [
        field for field, variable_type in schema.items() if variable_type is VariableType.NUMERIC
    ]
    if numeric_fields:
        descriptive = numeric_descriptives(analysis_frame, numeric_fields)
        st.subheader("连续数值字段")
        st.dataframe(
            descriptive,
            width="stretch",
            alt="连续数值字段描述统计",
        )
        st.caption(f"四分位数算法：{QUARTILE_ALGORITHM}")
    else:
        st.info("当前没有连续数值字段。")

    ordinal_fields = [
        field for field, variable_type in schema.items() if variable_type is VariableType.ORDINAL
    ]
    if ordinal_fields:
        ordinal = ordinal_descriptives(analysis_frame, ordinal_fields)
        st.subheader("有序字段")
        st.warning("有序字段按等级展示；不把均值或标准差作为默认指标。")
        st.dataframe(
            ordinal.summary,
            width="stretch",
            alt="有序字段中位数与四分位统计",
        )
        st.dataframe(
            ordinal.frequencies,
            width="stretch",
            alt="有序字段频数分布",
        )

    categorical_fields = [
        field
        for field, variable_type in schema.items()
        if variable_type is VariableType.CATEGORICAL
    ]
    if categorical_fields:
        selected_category = st.selectbox("分类字段频数", categorical_fields)
        st.dataframe(
            categorical_frequencies(analysis_frame, selected_category),
            width="stretch",
            alt="分类字段频数与有效百分比",
        )

with tabs[2]:
    numeric_fields = analysis_numeric_fields(schema)
    if len(numeric_fields) < 2:
        st.info("至少需要两个数值或有序字段。")
    else:
        left, right = st.columns(2)
        x_field = left.selectbox(
            "X 字段",
            numeric_fields,
            key="correlation_x",
            on_change=clear_correlation_result,
        )
        y_field = right.selectbox(
            "Y 字段",
            [field for field in numeric_fields if field != x_field],
            key="correlation_y",
            on_change=clear_correlation_result,
        )
        method_label = st.radio(
            "相关方法",
            ["Pearson", "Spearman"],
            horizontal=True,
            key="correlation_method",
            on_change=clear_correlation_result,
        )
        if schema[x_field] is VariableType.ORDINAL or schema[y_field] is VariableType.ORDINAL:
            st.warning("有序字段采用 Pearson 时仍需明确将分值视为等距尺度。")

        if st.button("计算相关", icon=":material/analytics:"):
            try:
                result = calculate_correlation(
                    analysis_frame,
                    x_field,
                    y_field,
                    method_label.lower(),
                    sampling_design,
                )
                st.session_state["correlation_result"] = result
            except ValueError as exc:
                st.error(str(exc))

        result = st.session_state.get("correlation_result")
        if result is not None and (
            result.sampling_design != sampling_design.value
            or result.x_field != x_field
            or result.y_field != y_field
            or result.method != method_label.lower()
        ):
            st.session_state["correlation_result"] = None
            result = None
        if result is not None:
            metric_columns = st.columns(3)
            metric_columns[0].metric("有效样本", f"{result.n:,}")
            metric_columns[1].metric("相关系数", f"{result.coefficient:.4f}")
            metric_columns[2].metric(
                "p 值",
                f"{result.p_value:.4g}" if result.p_value is not None else "未提供",
            )
            if result.p_value_reason:
                st.caption(result.p_value_reason)
            st.html(
                create_static_scatter_svg(
                    result.pair_data,
                    result.x_field,
                    result.y_field,
                )
            )
            for warning in result.warnings:
                st.warning(warning)
            if st.button("保存相关结果到项目", icon=":material/save:"):
                save_result(
                    store,
                    "correlation",
                    {
                        "x": result.x_field,
                        "y": result.y_field,
                        "method": result.method,
                        "sampling_design": result.sampling_design,
                    },
                    {
                        "n": result.n,
                        "coefficient": result.coefficient,
                        "p_value": result.p_value,
                        "p_value_reason": result.p_value_reason,
                    },
                )

with tabs[3]:
    item_candidates = analysis_numeric_fields(schema)
    if len(item_candidates) < 2:
        st.info("信度分析至少需要两个数值或有序题项。")
    else:
        selected_items = st.multiselect(
            "参与量表的题项",
            item_candidates,
            default=item_candidates[: min(3, len(item_candidates))],
            key="reliability_items",
            on_change=clear_reliability_result,
        )
        reverse_items = st.multiselect(
            "反向题",
            selected_items,
            help="只有明确配置反向的题项才会转换。",
            key="reliability_reverse_items",
            on_change=clear_reliability_result,
        )
        score_min, score_max = st.columns(2)
        minimum = score_min.number_input(
            "题项最小值",
            value=1.0,
            step=1.0,
            key="reliability_minimum",
            on_change=clear_reliability_result,
        )
        maximum = score_max.number_input(
            "题项最大值",
            value=5.0,
            step=1.0,
            key="reliability_maximum",
            on_change=clear_reliability_result,
        )
        if st.button("计算信度", icon=":material/fact_check:"):
            try:
                result = calculate_reliability(
                    analysis_frame,
                    selected_items,
                    reverse_items,
                    minimum,
                    maximum,
                    sampling_design,
                )
                st.session_state["reliability_result"] = result
            except ValueError as exc:
                st.error(str(exc))

        result = st.session_state.get("reliability_result")
        if result is not None and (
            result.sampling_design != sampling_design.value
            or list(result.items) != selected_items
            or list(result.reverse_items) != reverse_items
            or result.score_min != minimum
            or result.score_max != maximum
        ):
            st.session_state["reliability_result"] = None
            result = None
        if result is not None:
            metric_columns = st.columns(3)
            metric_columns[0].metric("完整样本", f"{result.n_complete:,}")
            metric_columns[1].metric("原始 α", f"{result.alpha:.4f}")
            metric_columns[2].metric("标准化 α", f"{result.standardized_alpha:.4f}")
            if not result.item_statistics.empty:
                st.dataframe(
                    result.item_statistics,
                    width="stretch",
                    alt="题项 CITC 与删除题项后的信度统计",
                )
            for warning in result.warnings:
                st.warning(warning)
            if st.button("保存信度结果到项目", icon=":material/save:"):
                save_result(
                    store,
                    "reliability",
                    {
                        "items": list(result.items),
                        "reverse_items": list(result.reverse_items),
                        "score_min": result.score_min,
                        "score_max": result.score_max,
                        "sampling_design": result.sampling_design,
                    },
                    {
                        "alpha": result.alpha,
                        "standardized_alpha": result.standardized_alpha,
                        "n_complete": result.n_complete,
                        "item_count": result.item_count,
                    },
                )

with tabs[4]:
    selected_fields = st.multiselect(
        "导出字段",
        list(analysis_frame.columns),
        default=list(analysis_frame.columns),
    )
    export_level = st.selectbox(
        "导出数据等级",
        options=list(DataLevel),
        index=None,
        placeholder="请选择数据等级",
        format_func=lambda level: level.label,
        key="export_level",
    )
    export_filename = f"{Path(st.session_state['source_name']).stem}_safe.csv"
    st.caption(f"目标文件：{export_filename}；浏览器将询问本地保存路径。")
    if export_level in {DataLevel.D1_R, DataLevel.D2, DataLevel.D3}:
        st.warning("该等级可能包含潜在披露、行级或受限数据，只允许本地导出。")
    export_confirmed = st.checkbox(
        "我已核对导出字段、数据等级和保存位置",
        key="export_confirmed",
    )
    if selected_fields and export_level is not None and export_confirmed:
        try:
            safe_csv = dataframe_to_safe_csv(analysis_frame, selected_fields)
            st.download_button(
                "下载安全 CSV",
                data=safe_csv.encode("utf-8-sig"),
                file_name=export_filename,
                mime="text/csv",
                icon=":material/download:",
            )
            st.caption("导出已执行公式注入防护；未上传任何在线服务。")
        except UnsafeCsvValueError as exc:
            st.error(f"导出已阻止：{exc}")
    else:
        st.info("选择字段、声明数据等级并确认后生成安全下载。")

with tabs[5]:
    st.subheader("Provider 状态")
    providers = ProviderRegistry().list_providers()
    for provider in providers:
        status_label = {
            ProviderStatus.NOT_CONFIGURED: "未配置",
            ProviderStatus.UNAVAILABLE: "不可用",
            ProviderStatus.VERIFIED: "已验证",
            ProviderStatus.DEGRADED: "降级",
        }[provider.status]
        st.markdown(f"**{provider.name}**：{status_label}")
        st.caption(provider.detail)

    st.subheader("在线发送边界")
    boundary_rows = []
    for level in DataLevel:
        decision = evaluate_online_boundary(level)
        boundary_rows.append(
            {
                "数据等级": level.label,
                "默认允许": "是" if decision.allowed else "否",
                "逐次授权": "是" if decision.requires_per_request_approval else "否",
                "单独例外审批": "是" if decision.requires_exception_approval else "否",
                "说明": decision.reason,
            }
        )
    st.dataframe(
        pd.DataFrame(boundary_rows),
        width="stretch",
        alt="在线 AI 数据等级发送边界",
        hide_index=True,
    )

    preview_level = st.selectbox(
        "预检数据等级",
        list(DataLevel),
        index=1,
        format_func=lambda level: level.label,
        key="boundary_data_level_selector",
    )
    exception_approved = st.checkbox(
        "本次 D1-R 请求已获得单独例外审批",
        value=False,
        disabled=preview_level is not DataLevel.D1_R,
        key="boundary_exception_approved",
    )
    request_approved = st.checkbox(
        "我授权本次请求使用上方数据等级",
        value=False,
        key="online_request_approved",
    )
    if st.button("生成在线请求预检", icon=":material/fact_check:"):
        aggregate = {
            "row_count": int(len(analysis_frame)),
            "column_count": int(len(analysis_frame.columns)),
        }
        payload = OnlineRequestPayload(
            provider="unconfigured-online",
            model="not-configured",
            request_url="https://provider.invalid/v1/chat/completions",
            system_prompt="解释统计摘要，不生成或修改数据。",
            user_prompt="请解释以下本地计算结果。",
            data=aggregate,
            attachments={},
            model_config={"temperature": 0, "max_tokens": 512},
        )
        try:
            authorized = build_authorized_request(
                payload,
                preview_level,
                user_approved=request_approved,
                exception_approved=exception_approved,
            )
        except AuthorizationError as exc:
            audit.record(
                "online_authorization",
                outcome="denied",
                data_level=preview_level.value,
            )
            st.error(str(exc))
        else:
            consistent = verify_authorized_payload(authorized, payload)
            disclosure_risk = st.session_state["disclosure_tracker"].register(preview_level)
            audit.record(
                "online_authorization",
                outcome="approved",
                data_level=preview_level.value,
                provider=payload.provider,
                fingerprint=authorized.fingerprint,
            )
            st.code(authorized.payload_json, language="json")
            st.caption(f"授权指纹：{authorized.fingerprint}")
            st.success(
                "预检载荷与授权内容一致；在线 Provider 当前未配置，因此没有发送请求。"
                if consistent
                else "载荷一致性校验失败，已阻止发送。"
            )
            if disclosure_risk:
                st.warning("本会话已出现多次授权预检；连续聚合、交叉表或差值可能产生组合披露风险。")

    st.subheader("方法引导")
    guidance = GuidanceService()
    suggestions = guidance.suggest_next_steps(
        numeric_fields=len(analysis_numeric_fields(schema)),
        categorical_fields=sum(
            variable_type is VariableType.CATEGORICAL for variable_type in schema.values()
        ),
        inference_allowed=sampling_design.allows_inference,
    )
    for suggestion in suggestions:
        st.info(suggestion)
    st.caption("当前未启用模型调用；AI Provider 不可用不会影响统计计算。")

with st.sidebar:
    st.divider()
    st.subheader("本地存储")
    st.code(str(workspace))
    st.caption(f"SQLite：{workspace / 'research_desk.sqlite3'}")
    st.caption("SQLite 未提供应用层加密，请依赖 Windows 用户权限和磁盘加密。")
