"""WRFT flyball 2023 analysis package.

Modules:
    config        paths, colour encodings, code maps, thresholds
    excel_reader  raw openpyxl reader (values + font colours)
    parse         title, day split and time-cell classification
    dogs          WRFT dog master data
    clean         builds the tidy tables and data-quality report
    metrics       Phase 3 tables: heat outcomes, team, start/pass and dog metrics
    stats         CIs, shrinkage, Holm, heat-win and dog run-time models
    plots         chart style and per-phase draft figures
"""
