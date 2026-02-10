#!/usr/bin/env python3
"""
Full Brazilian Legal Data Ingestion Script.
Populates HyPA-RAG with complete Brazilian legislation, sumulas, and jurisprudence.

Usage:
    python scripts/ingest_full_legislation.py [OPTIONS]

Options:
    --all               Ingest all data (default)
    --legislation       Ingest only legislation
    --sumulas           Ingest only sumulas
    --categories LIST   Filter legislation by categories (comma-separated)
    --clear             Clear existing data before ingestion
    --status            Show current ingestion status
    --dry-run           Show what would be ingested without executing

Categories available:
    constitucional, civil, penal, trabalhista, tributario, processual_civil,
    processual_penal, administrativo, consumidor, ambiental, empresarial,
    familia, previdenciario, eleitoral, militar, etc.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""

import asyncio
import argparse
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.database import qdrant_manager, neo4j_manager
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.retrieval.embeddings import get_embedding_model
from app.retrieval.legislation_parser import legislation_parser
from app.ingestion.unified_ingestor import UnifiedLegalIngestor
from app.ingestion.planalto_scraper import PlanaltoScraper, BRAZILIAN_LEGISLATION_CATALOG

# Configure logging
configure_logging()
logger = get_logger(__name__)


def print_banner():
    """Print startup banner."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║     SISTEMA DE LLM JUDICIAL - INGESTAO DE LEGISLACAO BRASILEIRA  ║
║                                                                  ║
║  HyPA-RAG Population Script                                      ║
║  Constituicao, Codigos, Leis, Sumulas                           ║
╚══════════════════════════════════════════════════════════════════╝
    """)


def show_catalog():
    """Show available legislation catalog."""
    scraper = PlanaltoScraper()

    print("\n📚 CATALOGO DE LEGISLACAO DISPONIVEL")
    print("=" * 60)

    # Group by category
    by_category = {}
    for leg in BRAZILIAN_LEGISLATION_CATALOG:
        cat = leg.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(leg)

    for category in sorted(by_category.keys()):
        print(f"\n🏷️  {category.upper()}")
        print("-" * 40)
        for leg in by_category[category]:
            print(f"  • {leg.id}: {leg.name}")

    print(f"\n📊 Total: {len(BRAZILIAN_LEGISLATION_CATALOG)} legislacoes")
    print(f"📂 Categorias: {', '.join(sorted(by_category.keys()))}")


async def show_status():
    """Show current ingestion status."""
    print("\n📊 STATUS DA INGESTAO")
    print("=" * 60)

    try:
        await qdrant_manager.connect()

        # Try Neo4j (optional)
        neo4j_connected = False
        try:
            await neo4j_manager.connect()
            neo4j_connected = True
        except Exception:
            pass

        embedding_model = get_embedding_model()

        ingestor = UnifiedLegalIngestor(
            qdrant_manager=qdrant_manager,
            neo4j_manager=neo4j_manager if neo4j_connected else None,
            embedding_model=embedding_model,
            legislation_parser=legislation_parser,
            settings=settings
        )
        ingestor._neo4j_available = neo4j_connected

        status = await ingestor.get_ingestion_status()

        print(f"\n🔢 Vetores no Qdrant: {status.get('vectors', 0)}")
        if qdrant_manager.is_local:
            print("   (armazenamento local)")

        if status.get('neo4j_available') and 'nodes' in status and status['nodes']:
            print("\n📈 Nos no Neo4j:")
            for node_type, count in status['nodes'].items():
                print(f"  • {node_type}: {count}")

            if 'edges' in status and status['edges']:
                print("\n🔗 Relacionamentos:")
                for edge_type, count in status['edges'].items():
                    print(f"  • {edge_type}: {count}")
        else:
            print("\n⚠ Neo4j nao disponivel - grafo desabilitado")

    except Exception as e:
        print(f"❌ Erro ao obter status: {e}")
    finally:
        await qdrant_manager.disconnect()
        try:
            await neo4j_manager.disconnect()
        except Exception:
            pass


async def run_ingestion(args):
    """Run the ingestion process."""
    print_banner()

    print("\n🚀 Iniciando processo de ingestao...")
    print(f"⏰ Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Connect to databases
        print("\n📡 Conectando aos bancos de dados...")
        await qdrant_manager.connect()
        if qdrant_manager.is_local:
            print("  ✓ Qdrant conectado (modo local)")
        else:
            print("  ✓ Qdrant conectado (servidor remoto)")

        # Try Neo4j (optional)
        neo4j_connected = False
        try:
            await neo4j_manager.connect()
            neo4j_connected = True
            print("  ✓ Neo4j conectado")
        except Exception as e:
            print(f"  ⚠ Neo4j indisponivel - continuando sem grafo: {e}")

        # Load embedding model
        print("\n🤖 Carregando modelo de embeddings...")
        embedding_model = get_embedding_model()
        print(f"  ✓ Modelo: {settings.embedding_model}")

        # Create ingestor
        ingestor = UnifiedLegalIngestor(
            qdrant_manager=qdrant_manager,
            neo4j_manager=neo4j_manager,
            embedding_model=embedding_model,
            legislation_parser=legislation_parser,
            settings=settings
        )

        # Clear data if requested
        if args.clear:
            print("\n🗑️  Limpando dados existentes...")
            await ingestor.clear_all_data()
            print("  ✓ Dados limpos")

        # Determine what to ingest
        include_legislation = args.all or args.legislation
        include_sumulas = args.all or args.sumulas

        categories = None
        if args.categories:
            categories = [c.strip() for c in args.categories.split(',')]
            print(f"\n🏷️  Categorias selecionadas: {', '.join(categories)}")

        # Run ingestion
        print("\n" + "=" * 60)
        print("📥 INICIANDO INGESTAO")
        print("=" * 60)

        stats = await ingestor.ingest_all(
            include_legislation=include_legislation,
            include_sumulas=include_sumulas,
            include_jurisprudence=False,  # Not yet implemented
            legislation_categories=categories,
            batch_size=100
        )

        # Print results
        print("\n" + "=" * 60)
        print("📊 RESULTADO DA INGESTAO")
        print("=" * 60)

        print(f"\n📜 Legislacao:")
        print(f"   Baixadas: {stats.legislation_fetched}")
        print(f"   Indexadas: {stats.legislation_indexed}")

        print(f"\n⚖️  Sumulas:")
        print(f"   Baixadas: {stats.sumulas_fetched}")
        print(f"   Indexadas: {stats.sumulas_indexed}")

        print(f"\n📈 Totais:")
        print(f"   Chunks processados: {stats.total_chunks}")
        print(f"   Vetores no Qdrant: {stats.total_vectors}")
        print(f"   Nos no Neo4j: {stats.total_graph_nodes}")

        if stats.errors:
            print(f"\n⚠️  Erros ({len(stats.errors)}):")
            for error in stats.errors[:10]:  # Show first 10 errors
                print(f"   • {error}")
            if len(stats.errors) > 10:
                print(f"   ... e mais {len(stats.errors) - 10} erros")

        duration = (stats.completed_at - stats.started_at).total_seconds()
        print(f"\n⏱️  Duracao: {duration:.1f} segundos")
        print(f"✅ Ingestao concluida com sucesso!")

        # Save stats to file
        stats_file = Path(__file__).parent / 'ingestion_stats.json'
        with open(stats_file, 'w') as f:
            json.dump(stats.to_dict(), f, indent=2, default=str)
        print(f"\n📄 Estatisticas salvas em: {stats_file}")

    except Exception as e:
        print(f"\n❌ Erro na ingestao: {e}")
        logger.exception("Ingestion failed")
        raise
    finally:
        await qdrant_manager.disconnect()
        await neo4j_manager.disconnect()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Ingestao completa de legislacao brasileira para o HyPA-RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Ingerir tudo (legislacao + sumulas)
  python scripts/ingest_full_legislation.py --all

  # Ingerir apenas legislacao civil e penal
  python scripts/ingest_full_legislation.py --legislation --categories civil,penal

  # Ingerir apenas sumulas
  python scripts/ingest_full_legislation.py --sumulas

  # Limpar e reingerir tudo
  python scripts/ingest_full_legislation.py --all --clear

  # Ver status atual
  python scripts/ingest_full_legislation.py --status

  # Ver catalogo disponivel
  python scripts/ingest_full_legislation.py --catalog
        """
    )

    parser.add_argument(
        '--all',
        action='store_true',
        default=True,
        help='Ingerir todos os dados (padrao)'
    )
    parser.add_argument(
        '--legislation',
        action='store_true',
        help='Ingerir apenas legislacao'
    )
    parser.add_argument(
        '--sumulas',
        action='store_true',
        help='Ingerir apenas sumulas'
    )
    parser.add_argument(
        '--categories',
        type=str,
        help='Categorias de legislacao (separadas por virgula)'
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Limpar dados existentes antes da ingestao'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Mostrar status atual da ingestao'
    )
    parser.add_argument(
        '--catalog',
        action='store_true',
        help='Mostrar catalogo de legislacao disponivel'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simular ingestao sem executar'
    )

    args = parser.parse_args()

    # Handle special commands
    if args.catalog:
        show_catalog()
        return

    if args.status:
        asyncio.run(show_status())
        return

    if args.dry_run:
        print_banner()
        print("\n🔍 MODO DRY-RUN (simulacao)")
        print("=" * 60)

        if args.legislation or args.all:
            scraper = PlanaltoScraper()
            catalog = scraper.get_catalog(
                categories=[c.strip() for c in args.categories.split(',')] if args.categories else None
            )
            print(f"\n📜 Legislacao a ser ingerida: {len(catalog)} documentos")
            for leg in catalog[:10]:
                print(f"   • {leg.name}")
            if len(catalog) > 10:
                print(f"   ... e mais {len(catalog) - 10}")

        if args.sumulas or args.all:
            print("\n⚖️  Sumulas a ser ingeridas:")
            print("   • ~58 Sumulas Vinculantes STF")
            print("   • ~736 Sumulas STF")
            print("   • ~660 Sumulas STJ")
            print("   • ~460 Sumulas TST")
            print("   • ~72 Sumulas TSE")

        print("\n✓ Dry-run concluido. Use sem --dry-run para executar.")
        return

    # Adjust flags if specific sources selected
    if args.legislation or args.sumulas:
        args.all = False

    # Run ingestion
    asyncio.run(run_ingestion(args))


if __name__ == "__main__":
    main()
