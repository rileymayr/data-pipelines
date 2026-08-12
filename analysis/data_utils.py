import io
import re
import pandas as pd

# Import pyodide for PyScript browser file handling
try:
    from pyodide.ffi import JsProxy
except ImportError:
    JsProxy = None


# Data Processing Functions


async def load_csv_data(
    file_input
) -> pd.DataFrame:
    """Reads local file paths, BytesIO, string streams, or PyScript browser inputs."""

    if file_input is None:
        raise ValueError("No file provided.")

    kwargs = {"header": 0, "skiprows": [1, 2]}

    # Handle PyScript Browser File objects
    if JsProxy and isinstance(file_input, JsProxy):
        array_buffer = await file_input.arrayBuffer()
        file_bytes = array_buffer.to_py()
        return pd.read_csv(io.BytesIO(file_bytes), **kwargs)

    # Handle local file paths (Jupyter testing)
    if isinstance(file_input, str):
        return pd.read_csv(file_input, **kwargs)

    # Handle bytes or file streams
    if isinstance(file_input, (bytes, io.BytesIO, io.StringIO)):
        return pd.read_csv(file_input, **kwargs)

    raise TypeError(f"Unsupported file input type: {type(file_input)}")


def load_csv_local(
    file_input
) -> pd.DataFrame:
    """Reads local file paths, BytesIO, or string streams."""

    if file_input is None:
        raise ValueError("No file provided.")
    return pd.read_csv(file_input, header=0, skiprows=[1, 2])


def drop_unfinished_surveys(
    df: pd.DataFrame
) -> pd.DataFrame:
    """Drops rows where the 'Progress' column is not equal to 100."""
    if "Progress" not in df.columns:
        raise ValueError("The DataFrame does not contain a 'Progress' column.")
    return df[df["Progress"] == 100]


def drop_no_names(
    df: pd.DataFrame
) -> pd.DataFrame:
    """Drops rows where the 'Name' column is empty or NaN."""
    if "Name" not in df.columns:
        raise ValueError("The DataFrame does not contain a 'Name' column.")
    return df[df["Name"].notna() & (df["Name"].str.strip() != "")]


def convert_category_to_int(
    df: pd.DataFrame, 
    cols_to_convert: list[str]
) -> pd.DataFrame:
    """Converts each column in cols_to_convert to nullable integers."""
    missing_columns = [col for col in cols_to_convert if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"The DataFrame does not contain the following columns: {', '.join(missing_columns)}"
        )

    for col in cols_to_convert:
        df[col] = df[col].astype("Int64")
    return df


def create_grouped_df(
    df: pd.DataFrame, 
    group_col: str, 
    value_col: str
) -> pd.DataFrame:
    """Formats DataFrame for plotting.

    Ensures group_col values are discrete strings and value_col values are numeric.
    """
    clean_df = df[[group_col, value_col]].copy()

    # Convert Hours to numeric, setting non-numeric errors to NaN
    clean_df[value_col] = pd.to_numeric(clean_df[value_col], errors="coerce")

    # Drop missing values in value_col
    clean_df = clean_df.dropna(subset=[value_col])

    # Format group_col as discrete strings (e.g., 2627.0 -> "2627")
    clean_df[group_col] = (
        pd.to_numeric(clean_df[group_col], errors="coerce")
        .astype("Int64")
        .astype(str)
    )

    return clean_df


def condense_branching_columns(
    df: pd.DataFrame
) -> pd.DataFrame:
    """Dynamically finds columns with 4-digit branch identifiers like '-2627' or '-XXXX',

    combines non-null values for each unique prefix/suffix pattern into a single column,
    and drops the original sparse branching columns.
    """
    df = df.copy()

    # Regex matches any 4-digit class code preceded by a hyphen
    pattern = re.compile(r"-\d{4}")

    # 1. Identify all columns that follow the branching pattern
    branch_cols = [col for col in df.columns if pattern.search(col)]

    if not branch_cols:
        return df

    # 2. Group columns by their base target name (stripping out '-XXXX')
    grouped_targets = {}
    for col in branch_cols:
        target_name = pattern.sub("", col)
        grouped_targets.setdefault(target_name, []).append(col)

    # 3. For each group, coalesce non-null values into a single series
    for target_name, cols in grouped_targets.items():
        # Stack matching columns and backfill across rows to pick the sole non-null value
        condensed_series = df[cols].bfill(axis=1).iloc[:, 0]

        # Insert/replace target column in DataFrame
        df[target_name] = condensed_series

        # Drop original sparse branching columns
        df.drop(columns=cols, inplace=True)

    return df


def pivot_weekly_survey_to_wide(
    df: pd.DataFrame,
    id_col: str,
    week_col: str,
    date_col: str,
    static_cols: list[str] | None = None,
    week_prefix: str = "W",
) -> pd.DataFrame:
    
    df = df.copy()

    if static_cols is None:
        static_cols = []

    # 1. Clean week numbers
    df[week_col] = pd.to_numeric(df[week_col], errors="coerce").astype("Int64")
    df = df.dropna(subset=[id_col, week_col])

    # 2. Sort by date and deduplicate to ensure strictly 1 row per (id_col, week_col)
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.sort_values(by=[id_col, week_col, date_col])

    df = df.groupby([id_col, week_col], as_index=False).last()

    # 3. Handle static columns and prevent duplicate column names in static_df
    valid_static = [
        col for col in static_cols if col in df.columns and col != id_col
    ]

    if valid_static:
        static_df = df.drop_duplicates(subset=[id_col], keep="last")[
            [id_col] + valid_static
        ]
    else:
        static_df = df[[id_col]].drop_duplicates()

    # Deduplicate columns in static_df if any duplicate headers exist
    static_df = static_df.loc[:, ~static_df.columns.duplicated()]

    # 4. Identify dynamic measures to pivot
    ignore_cols = {id_col, week_col} | set(valid_static)
    if date_col in df.columns:
        ignore_cols.add(date_col)

    weekly_measure_cols = [col for col in df.columns if col not in ignore_cols]

    # 5. Pivot dynamic measures
    pivoted = df.pivot(
        index=id_col, columns=week_col, values=weekly_measure_cols
    )

    # Flatten MultiIndex into ColName_W1, ColName_W2...
    pivoted.columns = [
        f"{col_name}_{week_prefix}{int(week_num)}"
        for col_name, week_num in pivoted.columns
    ]
    pivoted = pivoted.reset_index()

    # Deduplicate columns in pivoted if needed
    pivoted = pivoted.loc[:, ~pivoted.columns.duplicated()]

    # 6. Merge static demographics back with pivoted metrics
    final_df = pd.merge(static_df, pivoted, on=id_col, how="left")

    return final_df


# --- Pipeline Orchestrator ---


async def process_all_surveys(
    baseline_file,
    weekly_file,
    assessment_file=None,
    static_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Executes the full survey processing pipeline across all uploaded files."""
    
    # 1. Process Baseline Data
    baseline_df = await load_csv_data(baseline_file)
    baseline_df = drop_unfinished_surveys(baseline_df)
    baseline_df = drop_no_names(baseline_df)
    baseline_df = convert_category_to_int(baseline_df, ["Class Number"])

    # 2. Process Weekly Survey Data
    weekly_df = await load_csv_data(weekly_file)
    weekly_df = drop_unfinished_surveys(weekly_df)
    weekly_df = drop_no_names(weekly_df)
    weekly_df = convert_category_to_int(weekly_df, ["Class Number"])
    weekly_df = condense_branching_columns(weekly_df)

    # 3. Pivot Weekly Survey to Wide Format
    weekly_wide_df = pivot_weekly_survey_to_wide(
        weekly_df, id_col="Name", static_cols=static_cols
    )

    # 4. Merge Baseline with Pivoted Weekly Data
    final_df = pd.merge(baseline_df, weekly_wide_df, on="Name", how="outer")

    # 5. Optionally Merge Assessment Scores
    if assessment_file is not None:
        assessment_df = await load_csv_data(assessment_file)
        assessment_df = drop_no_names(assessment_df)
        final_df = pd.merge(final_df, assessment_df, on="Name", how="left")

    return final_df