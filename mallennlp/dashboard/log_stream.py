from pathlib import Path

import attr
from dash.exceptions import PreventUpdate
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html

from mallennlp.controllers.log_stream import format_log_line
from mallennlp.dashboard.page import Page
from mallennlp.exceptions import InvalidPageParametersError
from mallennlp.services.log_stream import LogStreamService
from mallennlp.services.serde import serde


@Page.register("/log-stream")
class LogStream(Page):
    @serde
    class SessionState:
        stream: LogStreamService

    @serde
    class Params:
        path: str = attr.ib()
        live: bool = False

        @path.validator
        def check_path_exists(self, attribute, value):
            if not Path(value).exists():
                raise InvalidPageParametersError(f"log file {value} not found")

    @classmethod
    def from_params(cls, params):
        stream = LogStreamService(
            params.path,
            max_lines=None,
            max_lines_per_update=None,
            max_blocks_per_update=None,
            max_block_size=-1,
        )
        return cls(cls.SessionState(stream=stream), params)

    def get_elements(self):
        elements = [
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            id="log-stream-content",
                            children=[
                                format_log_line(line)
                                for line in self.s.stream.readlines()
                            ],
                        ),
                        width=True,
                        className="dash-padded-element dash-element-no-hover",
                    )
                ]
            )
        ]
        if self.p.live:
            elements.append(
                dcc.Interval(id="log-stream-update-interval", interval=1000 * 1)
            )
        return elements

    @Page.callback(
        [Output("log-stream-content", "children")],
        [Input("log-stream-update-interval", "n_intervals")],
        mutating=True,
    )
    def render_log_stream_content(self, _):
        if not self.s.stream.should_read():
            raise PreventUpdate
        return [format_log_line(line) for line in self.s.stream.readlines()]
