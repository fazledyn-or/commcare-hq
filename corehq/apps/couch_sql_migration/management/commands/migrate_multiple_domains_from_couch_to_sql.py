import logging
import os

import attr

from django.core.management.base import BaseCommand, CommandError

from corehq.form_processor.utils import should_use_sql_backend
from corehq.form_processor.utils.general import (
    clear_local_domain_sql_backend_override,
)
from corehq.util.markup import SimpleTableWriter, TableRowFormatter

from ...couchsqlmigration import (
    CleanBreak,
    MigrationRestricted,
    do_couch_to_sql_migration,
    setup_logging,
)
from ...missingdocs import find_missing_docs
from ...progress import (
    couch_sql_migration_in_progress,
    set_couch_sql_migration_complete,
    set_couch_sql_migration_not_started,
    set_couch_sql_migration_started,
)
from ...statedb import open_state_db
from .migrate_domain_from_couch_to_sql import blow_away_migration

log = logging.getLogger(__name__)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('path')
        parser.add_argument('--state-dir',
            default=os.environ.get("CCHQ_MIGRATION_STATE_DIR"),
            required="CCHQ_MIGRATION_STATE_DIR" not in os.environ,
            help="""
                Directory for couch2sql logs and migration state. This must not
                reside on an NFS volume for migration state consistency.
                Can be set in environment: CCHQ_MIGRATION_STATE_DIR
            """)
        parser.add_argument('--strict', action='store_true', default=False,
            help="Abort domain migration even for diffs in deleted doc types")
        parser.add_argument('--live', action='store_true', default=False,
            help="Do live migration. Leave in unfinished state if there are "
                 "unpatchable diffs, otherwise patch, finish and commit.")

    def handle(self, path, state_dir, **options):
        self.strict = options['strict']
        self.live_migrate = options["live"]

        if not os.path.isfile(path):
            raise CommandError("Couldn't locate domain list: {}".format(path))

        with open(path, 'r', encoding='utf-8') as f:
            domains = [name.strip() for name in f.readlines() if name.strip()]

        failed = []
        log.info("Processing {} domains\n".format(len(domains)))
        for domain in domains:
            setup_logging(state_dir, f"migrate-{domain}")
            try:
                self.migrate_domain(domain, state_dir)
            except CleanBreak:
                failed.append((domain, "stopped by operator"))
                break
            except Incomplete as err:
                log.info("Incomplete migration: %s %s", domain, err)
                failed.append((domain, str(err)))
            except Exception as err:
                log.exception("Error migrating domain %s", domain)
                if not self.live_migrate:
                    self.abort(domain, state_dir)
                failed.append((domain, err))

        if failed:
            log.error("Errors:\n" + "\n".join(
                ["{}: {}".format(domain, exc) for domain, exc in failed]))
        else:
            log.info("All migrations successful!")

    def migrate_domain(self, domain, state_dir):
        if should_use_sql_backend(domain):
            log.info("{} already on the SQL backend\n".format(domain))
            return

        if couch_sql_migration_in_progress(domain, include_dry_runs=True):
            log.error("{} migration is in progress\n".format(domain))
            raise Incomplete("in progress")

        set_couch_sql_migration_started(domain, self.live_migrate)
        try:
            do_couch_to_sql_migration(
                domain,
                state_dir,
                with_progress=self.live_migrate,
                live_migrate=self.live_migrate,
            )
        except MigrationRestricted as err:
            log.error("migration restricted: %s", err)
            set_couch_sql_migration_not_started(domain)
            raise Incomplete(str(err))

        if self.live_migrate:
            self.finish_live_migration_if_possible(domain, state_dir)
        elif self.has_diffs(domain, state_dir):
            self.abort(domain, state_dir)
            raise Incomplete("has diffs")

        assert couch_sql_migration_in_progress(domain)
        set_couch_sql_migration_complete(domain)
        log.info(f"Domain migrated: {domain}\n")

    def finish_live_migration_if_possible(self, domain, state_dir):
        stats = get_diff_stats(domain, state_dir, self.strict)
        if stats:
            if any(s.pending for s in stats.values()):
                raise Incomplete("has pending diffs")
            assert any(s.patchable for s in stats.values()), stats
            log.info(f"Patching {domain} migration")
            do_couch_to_sql_migration(
                domain,
                state_dir,
                live_migrate=True,
                case_diff="patch",
            )
            if self.has_diffs(domain, state_dir, resume=True):
                raise Incomplete("has unpatchable or pending diffs")
        log.info(f"Finishing {domain} migration")
        set_couch_sql_migration_started(domain)
        do_couch_to_sql_migration(domain, state_dir)
        if self.has_diffs(domain, state_dir, resume=True):
            raise Incomplete("has diffs (WARNING: NOT LIVE!)")

    def has_diffs(self, domain, state_dir, resume=False):
        stats = get_diff_stats(domain, state_dir, self.strict, resume)
        if stats:
            header = "Migration has diffs: {}".format(domain)
            log.error(format_diff_stats(stats, header))
        return bool(stats)

    def abort(self, domain, state_dir):
        set_couch_sql_migration_not_started(domain)
        clear_local_domain_sql_backend_override(domain)
        blow_away_migration(domain, state_dir)


def get_diff_stats(domain, state_dir, strict, resume=False):
    DELETED_CASE = "CommCareCase-Deleted"
    find_missing_docs(domain, state_dir, resume=resume, progress=False)
    stats = {}
    with open_state_db(domain, state_dir) as statedb:
        for doc_type, counts in sorted(statedb.get_doc_counts().items()):
            if not strict and doc_type == DELETED_CASE and not counts.missing:
                continue
            if counts.diffs or counts.changes or counts.missing:
                stats[doc_type] = DiffStats(counts)
        pending = statedb.count_undiffed_cases()
        if pending:
            if "CommCareCase" not in stats:
                stats["CommCareCase"] = DiffStats(pending=pending)
            else:
                stats["CommCareCase"].pending = pending
    return stats


def format_diff_stats(stats, header=None):
    lines = []
    if stats:
        if header:
            lines.append(header)

        class stream:
            write = lines.append

        writer = SimpleTableWriter(stream, TableRowFormatter([30, 10, 10, 10]))
        writer.write_table(
            ['Doc Type', '# Couch', '# SQL', '# Docs with Diffs'],
            [(doc_type,) + stat.columns for doc_type, stat in stats.items()],
        )
    return "\n".join(lines)


@attr.s
class DiffStats:
    counts = attr.ib(default=None)
    pending = attr.ib(default=0)

    @property
    def columns(self):
        pending = f"{self.pending} pending" if self.pending else ""
        counts = self.counts
        if not counts:
            return "?", "?", pending
        diffs = counts.diffs + counts.changes
        if pending:
            diffs = f"{diffs} + {pending}" if diffs else pending
        return counts.total, counts.total + counts.missing, diffs

    @property
    def patchable(self):
        counts = self.counts
        return counts and (counts.missing + counts.diffs + counts.changes)


class Incomplete(Exception):
    pass
