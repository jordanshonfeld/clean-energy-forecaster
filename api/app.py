import json
from flask import Flask, jsonify, request
from flask_cors import CORS
## from terra.do
import datetime
import json
import requests

# 3rd party packages
from IPython import display
import pandas as pd


app = Flask(__name__)
CORS(app) 

default_end_date = datetime.date.today().isoformat()
default_start_date = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
default_start_date_for_avg = (datetime.date.today() - datetime.timedelta(days=50)).isoformat()
LOCAL_BALANCING_AUTHORITY = "MISO" #CHANGE BASED ON USER LOCATION (will need to handle post req)

def getData(default_start_date, balancing_authority):
    def get_eia_timeseries(
        url_segment,
        facets,
        value_column_name="value",
        start_date=default_start_date,
        end_date=default_end_date,
    ):
        """
        A generalized helper function to fetch data from the EIA API
        """
        EIA_API_KEY = "Cry1Zzkd94TGqiiXVc5lffvfGYoeYK2VFY0rJKk0"
        api_url = f"https://api.eia.gov/v2/electricity/rto/{url_segment}/data/?api_key={EIA_API_KEY}"

        response_content = requests.get(
            api_url,
            headers={
                "X-Params": json.dumps(
                    {
                        "frequency": "hourly",
                        "data": ["value"],
                        # "facets": dict(**{"timezone": ["Pacific"]}, **facets),
                        "facets": dict(**facets), #still need to figure out time zone
                        "start": start_date,
                        "end": end_date,
                        "sort": [{"column": "period", "direction": "desc"}],
                        "offset": 0,
                        "length": 5000,  # This is the maximum allowed
                    }
                )
            },
        ).json()

        # Sometimes EIA API responses are nested under a "response" key. Sometimes not 🤷
        if "response" in response_content:
            response_content = response_content["response"]

        # Handle warnings by displaying them to the user
        if "warnings" in response_content:
            display.display(
                display.Markdown(f"Warning(s) returned from EIA API:"),
                response_content["warnings"],
            )

        # Convert the data to a Pandas DataFrame and clean it up for plotting
        dataframe = pd.DataFrame(response_content["data"])
        dataframe["timestamp"] = dataframe["period"].apply(
            pd.to_datetime, format="%Y/%m/%dT%H"
        )
        dataframe.rename(columns={"value": value_column_name}, inplace=True)
        return dataframe


    def get_eia_grid_mix_timeseries(balancing_authorities, **kwargs):
        """
        Fetch electricity generation data by fuel type
        """
        return get_eia_timeseries(
            url_segment="fuel-type-data",
            facets={"respondent": balancing_authorities},
            value_column_name="Generation (MWh)",
            **kwargs,
        )


    def get_eia_net_demand_and_generation_timeseries(balancing_authorities, **kwargs):
        """
        Fetch electricity demand data
        """
        return get_eia_timeseries(
            url_segment="region-data",
            facets={
                "respondent": balancing_authorities,
                "type": ["D", "NG", "TI"],  # Filter out the "Demand forecast" (DF) type
            },
            value_column_name="Demand (MWh)",
            **kwargs,
        )


    def get_eia_interchange_timeseries(balancing_authorities, **kwargs):
        """
        Fetch electricity interchange data (imports & exports from other utilities)
        """
        return get_eia_timeseries(
            url_segment="interchange-data",
            facets={"toba": balancing_authorities},
            value_column_name=f"Interchange to local BA (MWh)",
            **kwargs,
        )

    local_generation_grid_mix = get_eia_grid_mix_timeseries(
        [balancing_authority],
        # Optional: uncomment the lines below to try looking at a different time range to get data from other seasons.
        # start_date="2022-01-01",
        # end_date="2022-12-01",
    )

    demand_df = get_eia_net_demand_and_generation_timeseries([balancing_authority])

    interchange_df = get_eia_interchange_timeseries([balancing_authority])

    # How much energy is both generated and consumed locally
    def get_energy_generated_and_consumed_locally(df):
        demand_stats = df.groupby("type-name")["Demand (MWh)"].sum()
        # If local demand is smaller than net (local) generation, that means: amount generated and used locally == Demand (net export)
        # If local generation is smaller than local demand, that means: amount generated and used locally == Net generation (net import)
        # Therefore, the amount generated and used locally is the minimum of these two
        return min(demand_stats["Demand"], demand_stats["Net generation"])


    energy_generated_and_used_locally = demand_df.groupby("timestamp").apply(
        get_energy_generated_and_consumed_locally
    )

    consumed_locally_column_name = "Power consumed locally (MWh)"

    # How much energy is imported and then used locally, grouped by the source BA (i.e. the BA which generated the energy)
    energy_imported_then_consumed_locally_by_source_ba = (
        interchange_df.groupby(["timestamp", "fromba"])[
            "Interchange to local BA (MWh)"
        ].sum()
        # We're only interested in data points where energy is coming *in* to the local BA, i.e. where net export is negative
        # Therefore, ignore positive net exports
        .apply(lambda interchange: max(interchange, 0))
    )

    # Combine these two together to get all energy used locally, grouped by the source BA (both local and connected)
    energy_consumed_locally_by_source_ba = pd.concat(
        [
            energy_imported_then_consumed_locally_by_source_ba.rename(
                consumed_locally_column_name
            ).reset_index("fromba"),
            pd.DataFrame(
                {
                    "fromba": balancing_authority, #maybe change back to LOCAL
                    consumed_locally_column_name: energy_generated_and_used_locally,
                }
            ),
        ]
    ).reset_index()

    all_source_bas = energy_consumed_locally_by_source_ba["fromba"].unique().tolist()

    # Then, fetch the fuel type breakdowns for each of those BAs
    generation_types_by_ba = get_eia_grid_mix_timeseries(all_source_bas).rename(
        {"respondent": "fromba", "type-name": "generation_type"}, axis="columns"
    )


    total_generation_by_source_ba = generation_types_by_ba.groupby(["timestamp", "fromba"])[
        "Generation (MWh)"
    ].sum()

    generation_types_by_ba_with_totals = generation_types_by_ba.join(
        total_generation_by_source_ba,
        how="left",
        on=["timestamp", "fromba"],
        rsuffix=" Total",
    )
    generation_types_by_ba_with_totals["Generation (% of BA generation)"] = (
        generation_types_by_ba_with_totals["Generation (MWh)"]
        / generation_types_by_ba_with_totals["Generation (MWh) Total"]
    )
    generation_types_by_ba_with_totals_and_source_ba_breakdown = generation_types_by_ba_with_totals.merge(
        energy_consumed_locally_by_source_ba.rename(
            {"Power consumed locally (MWh)": "Power consumed locally from source BA (MWh)"},
            axis="columns",
        ),
        on=["timestamp", "fromba"],
    )
    full_df_reindexed = (
        generation_types_by_ba_with_totals_and_source_ba_breakdown.set_index(
            ["timestamp", "fromba", "generation_type"]
        )
    )
    usage_by_ba_and_generation_type = (
        (
            full_df_reindexed["Power consumed locally from source BA (MWh)"]
            * full_df_reindexed["Generation (% of BA generation)"]
        )
        .rename("Usage (MWh)")
        .reset_index()
    )
    return usage_by_ba_and_generation_type

# HUZZAH ^^ behold usage_by_ba_and_generation_type

def processData(grid_mix_df):
    df = grid_mix_df

    df['hour'] = df['timestamp'].dt.hour

    # Group by hour and fuel type, and calculate the sum of 'Generation (MWh)' for each group
    grouped_data = df.groupby(['hour', 'generation_type'])['Usage (MWh)'].sum().reset_index()

    grouped_data['Usage (MWh)'] = grouped_data['Usage (MWh)'] / 6.0 #get avg (6 days)

    # Pivot the data to get fuel types as columns
    pivot_data = grouped_data.pivot(index='hour', columns='generation_type', values='Usage (MWh)').fillna(0)

    # Calculate the total generation for each hour
    pivot_data['total_generation'] = pivot_data.sum(axis=1)

    # # Calculate the percentage for each fuel type at each hour
    percentage_data = pivot_data.div(pivot_data['total_generation'], axis=0) * 100
    percentage_data['total_generation'] = pivot_data['total_generation']
    
# Calculate the sum of 'Solar', 'Wind', 'Hydro', 'Nuclear' for each row
    percentage_data["green_energy"] = percentage_data[
        ["Solar", "Wind", "Hydro", "Nuclear"]
    ].sum(axis=1) 
    # green_energy_data = percentage_data.sort_values(by=["green_energy"], ascending=False)
    return(percentage_data)


@app.route('/api/app', methods=['GET', 'POST'])
def get_schedule():
    if request.method == 'POST':
        # If the request is a POST, handle criteria passed in the JSON body
        ba = request.get_json()
        print("Received criteria:", ba)
        balancing_authority = ba.get("balancingAuthority")

            # If the request is a GET, process data with default criteria
        week_start_date = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        week_df = processData(getData(week_start_date, balancing_authority))

        month_start_date = (datetime.date.today() - datetime.timedelta(days=31)).isoformat()
        month_df = processData(getData(month_start_date, balancing_authority))
    else:
        week_start_date = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        week_df = processData(getData(week_start_date, LOCAL_BALANCING_AUTHORITY))

        month_start_date = (datetime.date.today() - datetime.timedelta(days=31)).isoformat()
        month_df = processData(getData(month_start_date, LOCAL_BALANCING_AUTHORITY))

    mean_green_energy = month_df["green_energy"].mean()
    std_green_energy = month_df["green_energy"].std()

            # Calculate Z-score and create a new column 'z_score'
    week_df["z_score"] = (week_df["green_energy"] - mean_green_energy) / std_green_energy

    return week_df.to_json()


if __name__ == '__main__':
    app.run(host="localhost", port=5000, debug=True)