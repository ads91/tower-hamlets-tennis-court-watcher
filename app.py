import dash
import logging
import argparse

import dash_bootstrap_components as dbc

from dash import html, dcc


app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server  # used by gunicorn webserver in Heroku production deployment

LOGGER = logging.getLogger(__name__)

DEFAULT_VERTICAL_SPACING = "50px"


def get_layout():
    # initial data for store component (dcc.Store instance)
    data = {
        "label": "Overview"
    }

    layout = dbc.Container(
        id="main-site-container",
        children=[
            dcc.Store(id="store", data=data),
            dbc.Row(
                dbc.Col(
                    children=html.P("<<app:tennis_booking>>"), width=True, align="center",
                ),
                justify="center"
            )
        ],
        fluid=True
    )

    return layout


# set app layout function
app.layout = get_layout


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default="8060")
    args, _ = parser.parse_known_args()
    LOGGER.info(f"Command line args are: {args.__dict__}")
    app.run_server(debug=False, **args.__dict__)
