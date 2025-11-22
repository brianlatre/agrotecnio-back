para cargar el seed en bash:

    docker compose exec api python -m app.seed_data

logs:

- hay que crear /logs a la altura de app
- hay que reiniciar el contenedor y ejecutarlo con --build para que instale la nueva dependencia "loguru" que controla los logs
