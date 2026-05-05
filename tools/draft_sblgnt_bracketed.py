#!/usr/bin/env python3
"""draft_sblgnt_bracketed.py — draft the NT verses that SBLGNT omits as
later additions (longer ending of Mark, pericope adulterae in John,
etc.) using Robinson-Pierpont 2005 Byzantine readings as source.

Cartha's primary NT source is SBLGNT, which omits or brackets ~30
verses that appear in the Byzantine / Textus Receptus / KJV tradition.
Excluding them entirely puts Cartha in a more aggressive textual-
critical position than NIV / ESV / NRSV (which include them with
brackets and a footnote). To "see the fullest view possible" while
keeping textual scholarship honest, we draft these 30 verses from the
Robinson-Pierpont 2005 Byzantine text and mark each with:

  source.edition: "rp2005-byzantine"
  textual_status: "secondary_witness"
  + a footnote explaining the textual-critical situation

Output: one verse YAML per ref under translation/nt/<slug>/<ch>/<v>.yaml.
Calls Gemini 3.1 Pro Preview via Vertex on cartha-bible-vertex (credit-
funded). Single-pass, ~30 API calls.

Usage:
    GOOGLE_APPLICATION_CREDENTIALS=~/.config/cartha/gemini-vertex-cbv.json \\
    GCP_LOCATION=global \\
    python3 tools/draft_sblgnt_bracketed.py            # dry-run, lists verses
    python3 tools/draft_sblgnt_bracketed.py --commit    # actually call + write
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation" / "nt"
DOCTRINE_PATH = REPO_ROOT / "DOCTRINE.md"
PHILOSOPHY_PATH = REPO_ROOT / "PHILOSOPHY.md"
MODEL = "gemini-3.1-pro-preview"
LOCATION = os.environ.get("GCP_LOCATION", "global")

# Book-slug → SBL 3-letter code
SLUG_TO_CODE = {
    "matthew": "MAT", "mark": "MRK", "luke": "LUK", "john": "JHN",
    "acts": "ACT", "romans": "ROM",
}
SLUG_TO_DISPLAY = {
    "matthew": "Matthew", "mark": "Mark", "luke": "Luke", "john": "John",
    "acts": "Acts", "romans": "Romans",
}

# The 30 verses, with Robinson-Pierpont 2005 Byzantine Greek readings.
# Where multiple major Byzantine witnesses agree, RP2005 is preferred;
# Stephanus 1550 TR is a fallback cited in the footnote when relevant.
BRACKETED_VERSES: list[dict] = [
    # Matthew
    {"slug": "matthew", "ch": 17, "v": 21,
     "greek": "Τοῦτο δὲ τὸ γένος οὐκ ἐκπορεύεται εἰ μὴ ἐν προσευχῇ καὶ νηστείᾳ.",
     "note": "Verse omitted by א*, B, Θ, 33, syr-s, copsa,bo. Present in C, D, K, L, W, Δ, Π, f1, f13, the Majority Text, the Latin tradition, and most Syriac witnesses. Likely a scribal harmonization to Mark 9:29."},
    {"slug": "matthew", "ch": 18, "v": 11,
     "greek": "Ἦλθεν γὰρ ὁ υἱὸς τοῦ ἀνθρώπου σῶσαι τὸ ἀπολωλός.",
     "note": "Verse omitted by א, B, L*, Θ*, f1, f13 33, copsa, copbo. Present in D, K, W, Δ, Π, the Majority Text, the Vulgate. Likely a scribal harmonization to Luke 19:10."},
    {"slug": "matthew", "ch": 23, "v": 14,
     "greek": "Οὐαὶ ὑμῖν, γραμματεῖς καὶ Φαρισαῖοι ὑποκριταί, ὅτι κατεσθίετε τὰς οἰκίας τῶν χηρῶν, καὶ προφάσει μακρὰ προσευχόμενοι· διὰ τοῦτο λήψεσθε περισσότερον κρίμα.",
     "note": "Verse omitted by א, B, D, L, Z, Θ, f1, copsa,bo. Present in W, 0102, 0107, f13, the Majority Text, the Old Latin and Vulgate, the Syriac tradition. Most modern critical editions place it after v.13 in some Byzantine witnesses, before v.13 in others — likely a scribal harmonization to Mark 12:40 / Luke 20:47."},
    # Mark
    {"slug": "mark", "ch": 7, "v": 16,
     "greek": "Εἴ τις ἔχει ὦτα ἀκούειν ἀκουέτω.",
     "note": "Verse omitted by א, B, L, Δ*, 0274, copsa, copbo-mss. Present in A, D, K, W, X, Θ, Π, f1, f13, 28, 700, the Majority Text, the Latin tradition, and most Syriac witnesses. The ear-saying formula recurs across the Synoptics; this instance may be scribal carry-over from Mark 4:9, 4:23."},
    {"slug": "mark", "ch": 9, "v": 44,
     "greek": "ὅπου ὁ σκώληξ αὐτῶν οὐ τελευτᾷ, καὶ τὸ πῦρ οὐ σβέννυται.",
     "note": "Verse omitted by א, B, C, L, W, Δ, Ψ, f1, copsa, copbo. Present in A, D, K, X, Θ, Π, f13, 28, 700, the Majority Text, the Latin tradition. Likely a scribal repetition of v.48, where the same line is preserved in all major witnesses."},
    {"slug": "mark", "ch": 9, "v": 46,
     "greek": "ὅπου ὁ σκώληξ αὐτῶν οὐ τελευτᾷ, καὶ τὸ πῦρ οὐ σβέννυται.",
     "note": "Verse omitted by א, B, C, L, W, Δ, Ψ, f1, copsa, copbo. Present in A, D, K, X, Θ, Π, f13, 28, 700, the Majority Text, the Latin tradition. Likely a scribal repetition of v.48, parallel to v.44."},
    {"slug": "mark", "ch": 11, "v": 26,
     "greek": "Εἰ δὲ ὑμεῖς οὐκ ἀφίετε, οὐδὲ ὁ πατὴρ ὑμῶν ὁ ἐν τοῖς οὐρανοῖς ἀφήσει τὰ παραπτώματα ὑμῶν.",
     "note": "Verse omitted by א, B, L, W, Δ, Ψ, 565, 700, copsa, copbo. Present in A, C, D, K, X, Θ, Π, f1, f13, 28, the Majority Text, the Latin tradition, and most Syriac witnesses. Likely a scribal harmonization to Matthew 6:15."},
    {"slug": "mark", "ch": 15, "v": 28,
     "greek": "Καὶ ἐπληρώθη ἡ γραφὴ ἡ λέγουσα, Καὶ μετὰ ἀνόμων ἐλογίσθη.",
     "note": "Verse omitted by א, A, B, C, D, X, Y, Ψ, copsa, copbo. Present in L, P, 083, 0250, f1, f13, 28, the Majority Text, the Latin tradition. Likely a scribal harmonization to Luke 22:37, citing Isaiah 53:12."},
    # Luke
    {"slug": "luke", "ch": 17, "v": 36,
     "greek": "Δύο ἔσονται ἐν τῷ ἀγρῷ· εἷς παραληφθήσεται, καὶ ὁ ἕτερος ἀφεθήσεται.",
     "note": "Verse omitted by א, A, B, L, W, Δ, Θ, Ψ, f1, 28, copsa, copbo. Present in D, f13, 700, 1071, the Majority Text, the Old Latin and Vulgate. Likely a scribal harmonization to Matthew 24:40."},
    {"slug": "luke", "ch": 23, "v": 17,
     "greek": "Ἀνάγκην δὲ εἶχεν ἀπολύειν αὐτοῖς κατὰ ἑορτὴν ἕνα.",
     "note": "Verse omitted by p75, A, B, K, L, T, the Sahidic Coptic. Present in א, D, W, Δ, Θ, Ψ, f1, f13, 700, the Majority Text, the Latin tradition. Some witnesses place it after v.18 instead. Likely a scribal harmonization to Matthew 27:15 / Mark 15:6."},
    # John
    {"slug": "john", "ch": 5, "v": 4,
     "greek": "Ἄγγελος γὰρ κατὰ καιρὸν κατέβαινεν ἐν τῇ κολυμβήθρᾳ, καὶ ἐτάρασσεν τὸ ὕδωρ· ὁ οὖν πρῶτος ἐμβὰς μετὰ τὴν ταραχὴν τοῦ ὕδατος, ὑγιὴς ἐγίνετο, ᾧ δήποτε κατείχετο νοσήματι.",
     "note": "Verse (along with the latter half of v.3) omitted by p66, p75, א, B, C*, D, T, W-supp, 33, copsa, copbo. Present in A, C3, K, L, X, Δ, Θ, Ψ, 0125, f1, f13, the Majority Text, the Latin tradition, the Syriac. Widely viewed as an early scribal explanation of why the disabled gathered at the pool."},
    # John 7:53–8:11 — the pericope adulterae
    {"slug": "john", "ch": 7, "v": 53,
     "greek": "Καὶ ἐπορεύθη ἕκαστος εἰς τὸν οἶκον αὐτοῦ.",
     "note": "First verse of the pericope adulterae (John 7:53–8:11). The whole pericope is omitted by p66, p75, א, A*, B, C*, L, N, T, W, X, Δ, Θ, Ψ, 33, 565, 1241, copsa, copbo, syrs, syrc. Present in D, K, M, U, Γ, f1 (after John 21:25), f13 (after Luke 21:38), 28, 700, 892, 1009, the Majority Text, the Latin tradition. Floats in different positions across manuscripts — clear evidence of an originally-independent oral tradition incorporated into the textual stream. Theologically and pastorally beloved across 1500 years of Christian reading; preserved here on those grounds with the textual evidence noted."},
    {"slug": "john", "ch": 8, "v": 1,
     "greek": "Ἰησοῦς δὲ ἐπορεύθη εἰς τὸ ὄρος τῶν Ἐλαιῶν.",
     "note": "Continuation of the pericope adulterae (John 7:53–8:11). See note on John 7:53 for textual evidence."},
    {"slug": "john", "ch": 8, "v": 2,
     "greek": "Ὄρθρου δὲ πάλιν παρεγένετο εἰς τὸ ἱερόν, καὶ πᾶς ὁ λαὸς ἤρχετο πρὸς αὐτόν· καὶ καθίσας ἐδίδασκεν αὐτούς.",
     "note": "Continuation of the pericope adulterae (John 7:53–8:11). See note on John 7:53."},
    {"slug": "john", "ch": 8, "v": 3,
     "greek": "Ἄγουσιν δὲ οἱ γραμματεῖς καὶ οἱ Φαρισαῖοι πρὸς αὐτὸν γυναῖκα ἐν μοιχείᾳ κατειλημμένην· καὶ στήσαντες αὐτὴν ἐν μέσῳ,",
     "note": "Continuation of the pericope adulterae (John 7:53–8:11). See note on John 7:53."},
    {"slug": "john", "ch": 8, "v": 4,
     "greek": "λέγουσιν αὐτῷ, Διδάσκαλε, αὕτη ἡ γυνὴ κατείληπται ἐπαυτοφώρῳ μοιχευομένη.",
     "note": "Continuation of the pericope adulterae (John 7:53–8:11). See note on John 7:53."},
    {"slug": "john", "ch": 8, "v": 5,
     "greek": "Ἐν δὲ τῷ νόμῳ ἡμῶν Μωσῆς ἐνετείλατο τὰς τοιαύτας λιθοβολεῖσθαι· σὺ οὖν τί λέγεις;",
     "note": "Continuation of the pericope adulterae (John 7:53–8:11). See note on John 7:53."},
    {"slug": "john", "ch": 8, "v": 6,
     "greek": "Τοῦτο δὲ ἔλεγον πειράζοντες αὐτόν, ἵνα ἔχωσιν κατηγορίαν κατ' αὐτοῦ. Ὁ δὲ Ἰησοῦς κάτω κύψας, τῷ δακτύλῳ ἔγραφεν εἰς τὴν γῆν, μὴ προσποιούμενος.",
     "note": "Continuation of the pericope adulterae (John 7:53–8:11). See note on John 7:53."},
    {"slug": "john", "ch": 8, "v": 7,
     "greek": "Ὡς δὲ ἐπέμενον ἐρωτῶντες αὐτόν, ἀνακύψας εἶπεν αὐτοῖς, Ὁ ἀναμάρτητος ὑμῶν, πρῶτος ἐπ' αὐτὴν τὸν λίθον βαλέτω.",
     "note": "Continuation of the pericope adulterae (John 7:53–8:11). See note on John 7:53."},
    {"slug": "john", "ch": 8, "v": 8,
     "greek": "Καὶ πάλιν κάτω κύψας ἔγραφεν εἰς τὴν γῆν.",
     "note": "Continuation of the pericope adulterae (John 7:53–8:11). See note on John 7:53."},
    {"slug": "john", "ch": 8, "v": 9,
     "greek": "Οἱ δὲ ἀκούσαντες, καὶ ὑπὸ τῆς συνειδήσεως ἐλεγχόμενοι, ἐξήρχοντο εἷς καθ' εἷς, ἀρξάμενοι ἀπὸ τῶν πρεσβυτέρων ἕως τῶν ἐσχάτων· καὶ κατελείφθη μόνος ὁ Ἰησοῦς, καὶ ἡ γυνὴ ἐν μέσῳ ἑστῶσα.",
     "note": "Continuation of the pericope adulterae (John 7:53–8:11). See note on John 7:53."},
    {"slug": "john", "ch": 8, "v": 10,
     "greek": "Ἀνακύψας δὲ ὁ Ἰησοῦς, καὶ μηδένα θεασάμενος πλὴν τῆς γυναικός, εἶπεν αὐτῇ, Ἡ γυνή, ποῦ εἰσιν ἐκεῖνοι οἱ κατήγοροί σου; Οὐδείς σε κατέκρινεν;",
     "note": "Continuation of the pericope adulterae (John 7:53–8:11). See note on John 7:53."},
    {"slug": "john", "ch": 8, "v": 11,
     "greek": "Ἡ δὲ εἶπεν, Οὐδείς, κύριε. Εἶπεν δὲ ὁ Ἰησοῦς, Οὐδὲ ἐγώ σε κατακρίνω· πορεύου, καὶ μηκέτι ἁμάρτανε.",
     "note": "Final verse of the pericope adulterae (John 7:53–8:11). See note on John 7:53."},
    # Acts
    {"slug": "acts", "ch": 8, "v": 37,
     "greek": "Εἶπεν δὲ ὁ Φίλιππος, Εἰ πιστεύεις ἐξ ὅλης τῆς καρδίας, ἔξεστιν. Ἀποκριθεὶς δὲ εἶπεν, Πιστεύω τὸν υἱὸν τοῦ θεοῦ εἶναι τὸν Ἰησοῦν Χριστόν.",
     "note": "Verse omitted by p45, p74, א, A, B, C, P, Ψ, 049, 33, 81, 614, 1739, 2412, copsa, copbo. Present in E, 4, 88, 181, 326, 436, 467, 629, 630, 945, 1505, 1877, the Latin tradition (Itala and some Vulgate witnesses), syrh-mg. Cited by Irenaeus and Cyprian in the late 2nd century. Often described as an early baptismal liturgical formula incorporated back into the Acts narrative."},
    {"slug": "acts", "ch": 15, "v": 34,
     "greek": "Ἔδοξε δὲ τῷ Σίλᾳ ἐπιμεῖναι αὐτοῦ.",
     "note": "Verse omitted by p74, א, A, B, E, Ψ, 33, 81, 1175, 1739, 2464, copsa, copbo. Present in C, D, 33-supp, 36, 88, 181, 307, 453, 614, 945, 1241, 1505, 1611, 1739-mg, 2412, 2495, the Latin tradition, syrh. Likely a scribal explanation for how Silas, who returns in v.40, could go with Paul if v.33 says he and Judas departed."},
    {"slug": "acts", "ch": 24, "v": 7,
     "greek": "παρελθὼν δὲ Λυσίας ὁ χιλίαρχος μετὰ πολλῆς βίας ἐκ τῶν χειρῶν ἡμῶν ἀπήγαγεν,",
     "note": "Verse (with the surrounding fuller reading of vv.6b–8a) omitted by p74, א, A, B, H, L, P, 049, 81, 1175, 1739, copsa, copbo. Present in E, Ψ, 33, 36, 323, 614, 945, 1241, 1505, 1611, the Latin tradition, syrh. Reads as an editorial expansion narrating Lysias's intervention before Felix."},
    {"slug": "acts", "ch": 28, "v": 29,
     "greek": "Καὶ ταῦτα αὐτοῦ εἰπόντος, ἀπῆλθον οἱ Ἰουδαῖοι, πολλὴν ἔχοντες ἐν ἑαυτοῖς συζήτησιν.",
     "note": "Verse omitted by p74, א, A, B, E, Ψ, 048, 33, 81, 1175, 1739, 2464, copsa, copbo. Present in 36, 307, 453, 614, 945, 1241, 1505, 1611, 2412, the Majority Text, the Latin and Syriac traditions. Likely a scribal expansion of the prior Jewish-leadership scene."},
    # Romans 16:25-27 — the doxology, which floats around in
    # different manuscript positions (after 14:23, after 15:33,
    # at the end of 16, or omitted). Included here at 16:25-27 per
    # the Byzantine / KJV / NA28-bracketed position.
    {"slug": "romans", "ch": 16, "v": 25,
     "greek": "Τῷ δὲ δυναμένῳ ὑμᾶς στηρίξαι κατὰ τὸ εὐαγγέλιόν μου καὶ τὸ κήρυγμα Ἰησοῦ Χριστοῦ, κατὰ ἀποκάλυψιν μυστηρίου χρόνοις αἰωνίοις σεσιγημένου,",
     "note": "First verse of the closing doxology (Romans 16:25–27). The doxology appears in different positions across manuscripts — after 14:23 (L, Ψ, the Majority Text); after 15:33 (p46); at the end of 16 (א, B, C, D, the Latin tradition); both at 14:23 and at the end of 16 (A, P, 33, 104); or omitted entirely (F, G, 629). Most modern critical editions place it at 16:25–27. Authenticity contested in 19th-century scholarship; widely retained in modern translations as Pauline."},
    {"slug": "romans", "ch": 16, "v": 26,
     "greek": "φανερωθέντος δὲ νῦν, διά τε γραφῶν προφητικῶν, κατ' ἐπιταγὴν τοῦ αἰωνίου θεοῦ, εἰς ὑπακοὴν πίστεως εἰς πάντα τὰ ἔθνη γνωρισθέντος,",
     "note": "Continuation of the closing doxology (Romans 16:25–27). See note on Romans 16:25."},
    {"slug": "romans", "ch": 16, "v": 27,
     "greek": "μόνῳ σοφῷ θεῷ, διὰ Ἰησοῦ Χριστοῦ, ᾧ ἡ δόξα εἰς τοὺς αἰῶνας. Ἀμήν.",
     "note": "Final verse of the closing doxology (Romans 16:25–27). See note on Romans 16:25."},
    # Mark 16:9-20 — the longer ending
    {"slug": "mark", "ch": 16, "v": 9,
     "greek": "Ἀναστὰς δὲ πρωῒ πρώτῃ σαββάτου ἐφάνη πρῶτον Μαρίᾳ τῇ Μαγδαληνῇ, ἀφ' ἧς ἐκβεβλήκει ἑπτὰ δαιμόνια.",
     "note": "First verse of the longer ending of Mark (16:9–20). The longer ending is omitted by א, B, 304, the Sinaitic Syriac, the Sahidic Coptic, two Sahidic mss; it has critical marks (asterisks/obeli) in many manuscripts that include it; and several manuscripts have a 'shorter ending' instead. Present in A, C, D, K, L, W, X, Δ, Θ, Π, Ψ, f13, 33, the Majority Text, the Latin tradition, the Curetonian Syriac, the Bohairic Coptic, the Armenian. Cited by Irenaeus and Tatian in the 2nd century. Distinctive vocabulary and abrupt narrative seam after v.8 are widely viewed as marks of secondary composition; nonetheless preserved in nearly all printed Greek and English Bibles since the Reformation."},
    {"slug": "mark", "ch": 16, "v": 10,
     "greek": "Ἐκείνη πορευθεῖσα ἀπήγγειλεν τοῖς μετ' αὐτοῦ γενομένοις, πενθοῦσιν καὶ κλαίουσιν.",
     "note": "Continuation of the longer ending of Mark (16:9–20). See note on Mark 16:9."},
    {"slug": "mark", "ch": 16, "v": 11,
     "greek": "Κἀκεῖνοι ἀκούσαντες ὅτι ζῇ καὶ ἐθεάθη ὑπ' αὐτῆς, ἠπίστησαν.",
     "note": "Continuation of the longer ending of Mark (16:9–20). See note on Mark 16:9."},
    {"slug": "mark", "ch": 16, "v": 12,
     "greek": "Μετὰ δὲ ταῦτα δυσὶν ἐξ αὐτῶν περιπατοῦσιν ἐφανερώθη ἐν ἑτέρᾳ μορφῇ, πορευομένοις εἰς ἀγρόν.",
     "note": "Continuation of the longer ending of Mark (16:9–20). See note on Mark 16:9."},
    {"slug": "mark", "ch": 16, "v": 13,
     "greek": "Κἀκεῖνοι ἀπελθόντες ἀπήγγειλαν τοῖς λοιποῖς· οὐδὲ ἐκείνοις ἐπίστευσαν.",
     "note": "Continuation of the longer ending of Mark (16:9–20). See note on Mark 16:9."},
    {"slug": "mark", "ch": 16, "v": 14,
     "greek": "Ὕστερον ἀνακειμένοις αὐτοῖς τοῖς ἕνδεκα ἐφανερώθη, καὶ ὠνείδισεν τὴν ἀπιστίαν αὐτῶν καὶ σκληροκαρδίαν, ὅτι τοῖς θεασαμένοις αὐτὸν ἐγηγερμένον οὐκ ἐπίστευσαν.",
     "note": "Continuation of the longer ending of Mark (16:9–20). See note on Mark 16:9."},
    {"slug": "mark", "ch": 16, "v": 15,
     "greek": "Καὶ εἶπεν αὐτοῖς, Πορευθέντες εἰς τὸν κόσμον ἅπαντα, κηρύξατε τὸ εὐαγγέλιον πάσῃ τῇ κτίσει.",
     "note": "Continuation of the longer ending of Mark (16:9–20). See note on Mark 16:9. This is the so-called 'Markan Great Commission'."},
    {"slug": "mark", "ch": 16, "v": 16,
     "greek": "Ὁ πιστεύσας καὶ βαπτισθεὶς σωθήσεται· ὁ δὲ ἀπιστήσας κατακριθήσεται.",
     "note": "Continuation of the longer ending of Mark (16:9–20). See note on Mark 16:9."},
    {"slug": "mark", "ch": 16, "v": 17,
     "greek": "Σημεῖα δὲ τοῖς πιστεύσασιν ταῦτα παρακολουθήσει· ἐν τῷ ὀνόματί μου δαιμόνια ἐκβαλοῦσιν· γλώσσαις λαλήσουσιν καιναῖς·",
     "note": "Continuation of the longer ending of Mark (16:9–20). See note on Mark 16:9."},
    {"slug": "mark", "ch": 16, "v": 18,
     "greek": "ὄφεις ἀροῦσιν· κἂν θανάσιμόν τι πίωσιν, οὐ μὴ αὐτοὺς βλάψει· ἐπὶ ἀρρώστους χεῖρας ἐπιθήσουσιν, καὶ καλῶς ἕξουσιν.",
     "note": "Continuation of the longer ending of Mark (16:9–20). See note on Mark 16:9. Source for some Pentecostal-Holiness handling-serpents practice; the textual situation is part of why mainstream Christian traditions read this verse cautiously."},
    {"slug": "mark", "ch": 16, "v": 19,
     "greek": "Ὁ μὲν οὖν κύριος Ἰησοῦς, μετὰ τὸ λαλῆσαι αὐτοῖς, ἀνελήφθη εἰς τὸν οὐρανόν, καὶ ἐκάθισεν ἐκ δεξιῶν τοῦ θεοῦ.",
     "note": "Continuation of the longer ending of Mark (16:9–20). See note on Mark 16:9."},
    {"slug": "mark", "ch": 16, "v": 20,
     "greek": "Ἐκεῖνοι δὲ ἐξελθόντες ἐκήρυξαν πανταχοῦ, τοῦ κυρίου συνεργοῦντος, καὶ τὸν λόγον βεβαιοῦντος διὰ τῶν ἐπακολουθούντων σημείων. Ἀμήν.",
     "note": "Final verse of the longer ending of Mark (16:9–20). See note on Mark 16:9."},
]


_vertex_token_cache: dict = {"token": None, "expiry": 0.0, "project": None}


def _vertex_token() -> tuple[str, str]:
    now = time.time()
    if _vertex_token_cache["token"] and _vertex_token_cache["expiry"] > now + 300:
        return _vertex_token_cache["token"], _vertex_token_cache["project"]
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not cred_path or not pathlib.Path(cred_path).exists():
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS must point at a SA JSON")
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    with open(cred_path) as fh:
        info = json.load(fh)
    project = info["project_id"]
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(Request())
    expiry = creds.expiry.timestamp() if getattr(creds, "expiry", None) else now + 3000
    _vertex_token_cache.update({"token": creds.token, "expiry": expiry, "project": project})
    return creds.token, project


def _vertex_call(prompt: str) -> dict:
    token, project = _vertex_token()
    api_host = "aiplatform.googleapis.com" if LOCATION == "global" else f"{LOCATION}-aiplatform.googleapis.com"
    url = f"https://{api_host}/v1/projects/{project}/locations/{LOCATION}/publishers/google/models/{MODEL}:generateContent"
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 8000,
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
    parts = resp.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "\n".join(p.get("text", "") for p in parts if "text" in p)
    return {"text": text, "usage": resp.get("usageMetadata", {})}


def _doctrine_excerpt() -> str:
    """Pull the most relevant doctrine snippet for translation philosophy."""
    if not PHILOSOPHY_PATH.exists():
        return ""
    txt = PHILOSOPHY_PATH.read_text(encoding="utf-8")
    return txt[:3000]


def _build_prompt(entry: dict) -> str:
    slug = entry["slug"]
    ch, v = entry["ch"], entry["v"]
    code = SLUG_TO_CODE[slug]
    display = SLUG_TO_DISPLAY[slug]
    greek = entry["greek"]
    crit_note = entry["note"]
    return f"""You are translating one verse for the People's Open Bible — a CC-BY 4.0 English Bible translated directly from original-language sources.

This verse is one of ~30 New Testament verses that the SBLGNT critical edition omits as a later addition, but that the Byzantine textual tradition (and the KJV / NIV / ESV / NRSV with bracket-and-footnote conventions) preserves. Cartha is including these verses with explicit textual-critical footnotes so readers see the fullest received tradition while remaining transparent about manuscript evidence.

REFERENCE: {display} {ch}:{v}
SBL CODE: {code}.{ch}.{v}
GREEK SOURCE (Robinson-Pierpont 2005 Byzantine reading):
{greek}

TEXTUAL-CRITICAL EVIDENCE (must be the substance of the footnote):
{crit_note}

CARTHA TRANSLATION PHILOSOPHY (excerpt):
{_doctrine_excerpt()}

Produce a single JSON object — no markdown fences, no preamble — with this exact shape:

{{
  "english_text": "<the English translation of the verse, optimal-equivalence philosophy, footnote markers like [a] [b] inline where lexical_decisions warrant>",
  "philosophy": "optimal-equivalence",
  "footnotes": [
    {{
      "marker": "a",
      "text": "<short reader-facing footnote — for textual-critical verses always include a note explaining the manuscript situation in plain English>",
      "reason": "textual_critical | alternative_reading | lexical_choice | etc."
    }}
  ],
  "lexical_decisions": [
    {{
      "source_word": "<Greek lemma>",
      "chosen": "<chosen English>",
      "alternatives": ["<plausible alternative renderings>"],
      "lexicon": "BDAG | LSJ | Louw-Nida",
      "rationale": "<why this rendering, in 1-2 sentences>"
    }}
  ],
  "theological_decisions": []
}}

Hard requirements:
- The first footnote (marker [a]) must be the textual-critical footnote, summarizing the evidence above in clean plain English (no manuscript siglum strings the average reader can't parse — instead say things like "absent from the earliest Greek manuscripts (4th-century Vaticanus, 4th-century Sinaiticus) but present in the Byzantine majority tradition and cited by Irenaeus in the 2nd century"). Always anchor the [a] marker on the verse's first content word.
- For the pericope adulterae (John 7:53–8:11) and the longer ending of Mark (16:9–20), the [a] footnote on the first verse of each block should include the full evidence; subsequent verses can carry a brief "See note on John 7:53." style cross-reference.
- Translation should be reverent but readable English, true to the Greek's syntax and word order where natural.
- Do not introduce footnote markers in the english_text that aren't backed by entries in the footnotes array.
- All Greek lemmas in lexical_decisions must come from the Greek source above (no inventing words).

Return ONLY the JSON object."""


def _build_yaml_payload(entry: dict, model_response: dict, model_id: str) -> dict:
    slug = entry["slug"]
    ch, v = entry["ch"], entry["v"]
    code = SLUG_TO_CODE[slug]
    display = SLUG_TO_DISPLAY[slug]
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": f"{code}.{ch}.{v}",
        "reference": f"{display} {ch}:{v}",
        "source": {
            "edition": "robinson-pierpont-2005-byzantine",
            "text": entry["greek"],
            "language": "Greek",
        },
        "translation": {
            "text": model_response["english_text"],
            "philosophy": model_response.get("philosophy", "optimal-equivalence"),
            "footnotes": model_response.get("footnotes", []),
        },
        "lexical_decisions": model_response.get("lexical_decisions", []),
        "theological_decisions": model_response.get("theological_decisions", []) or [],
        "ai_draft": {
            "model_id": model_id,
            "model_version": model_id,
            "prompt_id": "sblgnt_bracketed_v1_2026-04-27",
            "timestamp": now,
            "temperature": 0.2,
        },
        "status": "drafted",
        "textual_status": "secondary_witness",
        "critical_text_note": entry["note"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true",
                        help="Actually call Vertex + write YAMLs (default: dry-run)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Cap the number of verses processed (0 = all)")
    parser.add_argument("--only", default="",
                        help="Restrict to verses in book(s); comma-separated slugs (e.g. 'mark,john')")
    args = parser.parse_args()

    entries = list(BRACKETED_VERSES)
    if args.only:
        keep = {s.strip() for s in args.only.split(",")}
        entries = [e for e in entries if e["slug"] in keep]
    if args.limit:
        entries = entries[:args.limit]

    print(f"SBLGNT-bracketed verses to draft: {len(entries)}")
    by_book: dict[str, int] = {}
    for e in entries:
        by_book[e["slug"]] = by_book.get(e["slug"], 0) + 1
    for b, n in by_book.items():
        print(f"  {b}: {n}")

    if not args.commit:
        print("\nDRY RUN — pass --commit to call Vertex Gemini 3.1 Pro Preview and write YAMLs.")
        return 0

    written = 0
    errors = 0
    for entry in entries:
        slug = entry["slug"]
        ch, v = entry["ch"], entry["v"]
        target = TRANSLATION_ROOT / slug / f"{ch:03d}" / f"{v:03d}.yaml"
        if target.exists():
            print(f"  skip (exists): {target.relative_to(REPO_ROOT)}")
            continue
        prompt = _build_prompt(entry)
        try:
            resp = _vertex_call(prompt)
        except Exception as e:
            print(f"  ERROR {entry['slug']} {ch}:{v}: {type(e).__name__}: {e}")
            errors += 1
            continue
        try:
            model_response = json.loads(resp["text"])
        except json.JSONDecodeError as e:
            print(f"  ERROR {entry['slug']} {ch}:{v}: bad JSON from model: {e}; raw[:200]={resp['text'][:200]}")
            errors += 1
            continue
        payload = _build_yaml_payload(entry, model_response, MODEL)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=10000),
            encoding="utf-8",
        )
        written += 1
        usage = resp.get("usage", {})
        print(f"  ✓ {entry['slug']} {ch}:{v} — tokens={usage.get('totalTokenCount', '?')}")

    print(f"\nDone. Written: {written}, errors: {errors}, total target: {len(entries)}.")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
