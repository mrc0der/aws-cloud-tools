import requests

# https://awslabs.github.io/aws-crt-python/api/http.html#awscrt.http.HttpRequest
from awscrt.http import HttpRequest

"""
This is a example way to query for your AWS Support plan

Orig: https://www.sktan.com/blog/post/7-determining-your-aws-support-level-via-the-supportplans-api
"""

http_request = HttpRequest(method="GET", path="/v1/getSupportPlan")
http_request.headers.add("Host", "service.supportplans.us-east-2.api.aws")

# https://awslabs.github.io/aws-crt-python/api/auth.html
from awscrt.auth import (
    AwsCredentialsProvider,
    AwsSignatureType,
    AwsSigningAlgorithm,
    AwsSigningConfig,
    aws_sign_request,
)

result: HttpRequest = aws_sign_request(
    http_request=http_request,
    signing_config=AwsSigningConfig(
        algorithm=AwsSigningAlgorithm.V4,
        signature_type=AwsSignatureType.HTTP_REQUEST_HEADERS,
        credentials_provider=AwsCredentialsProvider.new_default_chain(),
        service="supportplans",
        region="us-east-2",
    ),
).result()


response = requests.get(
    url="https://service.supportplans.us-east-2.api.aws/v1/getSupportPlan",
    headers=dict(result.headers),
)

print(f"Your AWS support level is: {response.json()['supportPlan']}")
