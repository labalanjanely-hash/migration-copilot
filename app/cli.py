import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from app.config import get_settings
from app.services.pipeline import MigrationPipeline, PipelineValidationError
from app.storage import SQLiteAuditRepository
from engines.ingestion import CsvIngestionEngine
from models.records import ExportType, IngestionRequest
from reports.bundle import ReportBundleWriter
from reports.source_register import SourceRegisterWriter
from rules.configuration import PipelineConfiguration

cli = typer.Typer(no_args_is_help=True, help="Read-only Kajabi migration copilot.")


@cli.command()
def info() -> None:
    settings = get_settings()
    typer.echo(f"{settings.app_name} 0.1.0")
    typer.echo("mode=read_only_mvp release=NO_GO external_writes=disabled")


@cli.command("inspect-csv")
def inspect_csv(
    source: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False)],
    export_type: Annotated[ExportType, typer.Option()],
    output: Annotated[Path, typer.Option()] = Path("outputs/source-register.json"),
    required_column: Annotated[list[str] | None, typer.Option("--required-column")] = None,
) -> None:
    requests = [
        IngestionRequest(
            path=path,
            export_type=export_type,
            required_columns=tuple(required_column or ()),
        )
        for path in source
    ]
    result = CsvIngestionEngine().execute(requests)
    typer.echo(f"source_register={SourceRegisterWriter().write(result, output)}")
    typer.echo(f"status={'valid' if result.is_valid else 'review_required'}")
    if not result.is_valid:
        raise typer.Exit(2)


@cli.command("run-pipeline")
def run_pipeline(
    source: Annotated[list[str], typer.Option("--source")],
    configuration: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    output_directory: Annotated[Path, typer.Option()] = Path("outputs"),
    database: Annotated[Path, typer.Option()] = Path("migration_copilot.db"),
) -> None:
    config = PipelineConfiguration.model_validate_json(configuration.read_text(encoding="utf-8"))
    requests: list[IngestionRequest] = []
    for specification in source:
        export_name, separator, raw_path = specification.partition("=")
        if not separator:
            raise typer.BadParameter("Use export_type=/path/file.csv syntax.")
        export_type = ExportType(export_name)
        mapping = config.fields_by_record_type.get(export_type.value)
        if mapping is None:
            raise typer.BadParameter(f"No mapping configured for {export_type.value}.")
        columns = tuple(value for value in mapping.model_dump().values() if isinstance(value, str))
        requests.append(
            IngestionRequest(
                path=Path(raw_path),
                export_type=export_type,
                required_columns=columns,
                expected_columns=columns,
            )
        )
    try:
        result = MigrationPipeline(config).run(requests)
    except PipelineValidationError as exc:
        typer.echo(f"pipeline_status=blocked reason={exc}", err=True)
        raise typer.Exit(2) from exc
    SQLiteAuditRepository(database).save(result)
    artifacts = ReportBundleWriter().write(result, output_directory)
    typer.echo(f"run_id={result.run_id}")
    typer.echo(f"release_status={result.release_status}")
    for artifact in artifacts:
        typer.echo(f"artifact={artifact}")


@cli.command()
def advise(
    run_id: Annotated[str, typer.Option()],
    database: Annotated[Path, typer.Option()] = Path("migration_copilot.db"),
    inventory: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "docs/asset-inventory.example.json"
    ),
) -> None:
    from dotenv import load_dotenv

    load_dotenv(".env.local", override=False)
    load_dotenv(".env", override=False)
    from app.ai.migration_advisor import (
        AdvisorUnavailableError,
        MigrationAdvisor,
        MigrationAdvisorConfig,
    )

    advisor = MigrationAdvisor(
        MigrationAdvisorConfig(
            model=get_settings().openai_model, database_path=database, inventory_path=inventory
        )
    )
    try:
        report = asyncio.run(advisor.advise(run_id))
    except AdvisorUnavailableError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(3) from exc
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2))


@cli.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run("app.api:app", host=host, port=port)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
