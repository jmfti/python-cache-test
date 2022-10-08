echo "Executing ${ENV_APP_NAME}.py with args ${ENV_APP_ARGS}"
LOGLEVEL="error"
if [ "${ENVIRONMENT}" = "DEV" ]; then
    LOGLEVEL="debug"
    # do other things? if dev better to mock db? dev -> mock & pre -> db?
fi
#echo "gunicorn -w 2 -k uvicorn.workers.UvicornH11Worker --chdir /app --bind 0.0.0.0:5000 --log-level ${LOGLEVEL} ${ENV_APP_NAME}:app"
gunicorn -w 2 -k uvicorn.workers.UvicornH11Worker --workers ${WORKERS} --reload-engine auto --chdir /app --bind 0.0.0.0:8000 --log-level ${LOGLEVEL} ${ENV_APP_NAME}:app --reload