FROM python:3.6-alpine as build
RUN apk update
RUN apk add build-base
COPY requirements.txt .
RUN pip install -r requirements.txt

#FROM python:3-alpine
RUN wget -P /usr/local/bin https://storage.googleapis.com/kubernetes-release/release/v1.10.3/bin/linux/amd64/kubectl
RUN chmod +x /usr/local/bin/kube*
#COPY --from=build /root/.cache /root/.cache
#COPY --from=build requirements.txt .
#RUN pip install -r requirements.txt && rm -rf /root/.cache

COPY app /app
RUN python -m compileall /app
ENTRYPOINT ["python","/app/deploy.py"]
