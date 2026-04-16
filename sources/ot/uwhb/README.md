<img src="https://cdn.door43.org/assets/uw-icons/logo-uhb-256.png" alt="drawing" width="100"/>

# unfoldingWord® Hebrew Bible

*An open-licensed, lexically tagged, morphologically parsed Hebrew Old Testament. It enables the global Church to have access to the original texts of the Old Testament.*

## Basis

The UHB is based on the [Open Scriptures Hebrew Bible](https://github.com/openscriptures/morphhb) (OSHB) version 2.1. The OSHB project is the Westminster Leningrad Codex (WLC) with Strongs lexical data and morphological data marked up in OSIS files.

## Changes from the OSHB

The UHB differs from the OSHB in a few respects (though more may be coming):

* Metadata—The UHB text includes various metadata to mark the text which create links to other content that our software uses. For example, we add links to our [unfoldingWord® Translation Words](https://git.door43.org/unfoldingWord/en_tw) articles where appropriate.
* Joined words (for example: inseparable prepositions, the definite article, conjunctive waw) are separated using a unicode WORD JOINER (U+2060) character instead of the `/` character that the OSHB uses.
* The UHB is encoded in [USFM 3.0](https://ubsicap.github.io/usfm/) instead of the OSIS that the OSHB uses.
* The UHB uses the versification scheme of the [ULT](https://git.door43.org/unfoldingWord/en_ult) instead of that of the OSHB (which is based on the WLC scheme common for Hebrew Bibles). The goal of this change is to simplify the translation and reference process for Gateway Language teams and supplemental resources (such as our translation helps suite). This may make some resources that are keyed to the WLC more difficult to use with the Hebrew text but it will likely simplify the use of many other resources that use an ASV/KJV style of versification.
* For each Ketiv/Qere occurrence, we have selected one of the forms for the main body of the text and have footnoted the other.
* In some instances, the UHB selects alternate readings (either in the text or in the footnotes) from the OSHB, usually on the basis of manuscripts other than the Leningrad Codex. These references include: Gen 13:10; Ruth 3:12, 3:15, 4:4; 2 Sam 2:9, 5:8, 22:8, 23:8; 1 Ki 12:12; 1 Chr 9:4; Isa 53:11; Jer 2:21, 6:6, 8:6, 8:10 [x2], 15:10, 18:16; Nah 2:1.

## Related projects

* [unfoldingWord® Hebrew Grammar (UHG)](https://uhg.readthedocs.io/en/latest/)
* [unfoldingWord® Literal Text (ULT)](https://git.door43.org/unfoldingWord/en_ult)
