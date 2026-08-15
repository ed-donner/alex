"""
Lambda function to trigger App Runner research endpoint.
Called by EventBridge on a schedule.
"""
import os
import urllib.request
import json
import loguru
import urllib
from http import HTTPStatus
from urllib.request import Request
from typing import Any, Dict

from config.constants import DEFAULT_LAMBDA_REQUEST_TIMEOUT

_LOGGER = loguru.logger

def handler(event, context):
    """Trigger the research endpoint on App Runner."""
    _LOGGER.info(f"Received scheduler trigger event: {event}")
    
    app_runner_url = os.environ.get('APP_RUNNER_URL')
    if not app_runner_url:
        msg = "`APP_RUNNER_URL` environment variable not set"
        _LOGGER.debug(msg)
        raise ValueError(msg)

    # Remove any extra protocol info
    app_runner_url = _normalize_url(app_runner_url)
    url = f"https://{app_runner_url}/research"

    try:
        # Extract schedule context passed from EventBridge target payload
        schedule_context = {}
        if isinstance(event, dict):
            if "schedule_expression" in event:
                schedule_context["schedule_expression"] = event["schedule_expression"]
            if "schedule_expression_timezone" in event:
                schedule_context["schedule_expression_timezone"] = event["schedule_expression_timezone"]

        data = json.dumps(schedule_context).encode('utf-8')
        return _trigger_lambda_request(
            req=_make_request(url, data),
            req_timeout=DEFAULT_LAMBDA_REQUEST_TIMEOUT
        )

    except Exception as e:
        print(f"Error triggering research: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def _trigger_lambda_request(req: Request, req_timeout: int) -> Any | Dict:
    """
    Trigger the Lambda.

    :param req: The request to trigger.
    :param req_timeout: Timeout to send to aws sdk.

    :return: Object payload of response.
    :raise: Exception. Return runtime exceptions to the caller.
    """
    with urllib.request.urlopen(req, timeout=req_timeout) as response:
        _LOGGER.info(f"Triggering lambda with timeout of f{req_timeout}")
        _LOGGER.debug(f'Sending request f{req} with payload {req.data}')

        result = response.read().decode('utf-8')

        _LOGGER.info(f"Research triggered successfully: {result}")

        return {
            'statusCode': HTTPStatus.OK,
            'body': json.dumps({
                'message': 'Research triggered successfully',

                'result': result
            })
        }


def _make_request(url: str, data: bytes) -> Request:
    """
    Form and return a urllib Request object.

    :param url: url.
    :param data: Request body data, as bytes.
    :return: The formed `Request`.
    """
    req: Request = urllib.request.Request(
        url,
        data=data,
        method='POST',
        headers={'Content-Type': 'application/json'}
    )
    return req


def _normalize_url(url: str) -> str:
    """
    Normalize the URL by Removing any HTTPx identifiers
    from the start of the url.

    :param url: URL to normalize.
    :return: Normalized URL, with HTTPx identifiers
             from the start of the url,
    or the url itself if it doesn't start with HTTPx.
    """
    if url.startswith('https://'):
        return url.replace('https://', '')
    elif url.startswith('http://'):
        return url.replace('http://', '')
    else:
        raise ValueError('Invalid url scheme')
