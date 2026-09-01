# OOXML schemas — ISO/IEC 29500-4:2016

The PresentationML schema and its transitive imports, used by
`tests/test_ooxml_schema.py` to validate the raw XML `deckwright.motion` writes.

`deckwright` authors `<p:timing>` and `<p:transition>` as raw strings, because
python-pptx models neither. Nothing else can check that output: LibreOffice
converts schema-invalid timing to PDF without complaint, and a `deckwright qa`
render sees only the final state of a slide.

Nine files, the closure of `pml.xsd`'s `schemaLocation` imports. They are not
packaged into the wheel, but they do ship in the sdist, which carries a
runnable suite — `tests/test_ooxml_schema.py` fails rather than skips when the
schema is absent, so the notice below travels with them.

Published by Ecma International as part of ECMA-376 (also ISO/IEC 29500),
available at no charge from
https://ecma-international.org/publications-and-standards/standards/ecma-376/

## Copyright notice

Reproduced as Ecma's copyright policy requires of every copy. This is the
default notice, from
https://ecma-international.org/policies/by-ipr/ecma-text-copyright-policy/

> COPYRIGHT NOTICE
>
> © Ecma International
>
> By obtaining and/or copying this work, you (the licensee) agree that you have
> read, understood, and will comply with the following terms and conditions.
>
> This document may be copied, published and distributed to others, and certain
> derivative works of it may be prepared, copied, published, and distributed, in
> whole or in part, provided that the above copyright notice and this Copyright
> License and Disclaimer are included on all such copies and derivative works.
> The only derivative works that are permissible under this Copyright License and
> Disclaimer are:
>
> (i) works which incorporate all or portion of this document for the purpose of
> providing commentary or explanation (such as an annotated version of the
> document),
>
> (ii) works which incorporate all or portion of this document for the purpose of
> incorporating features that provide accessibility,
>
> (iii) translations of this document into languages other than English and into
> different formats and
>
> (iv) works by making use of this specification in standard conformant products
> by implementing (e.g. by copy and paste wholly or partly) the functionality
> therein.
>
> However, the content of this document itself may not be modified in any way,
> including by removing the copyright notice or references to Ecma International,
> except as required to translate it into languages other than English or into a
> different format.
>
> The official version of an Ecma International document is the English language
> version on the Ecma International website. In the event of discrepancies between
> a translated version and the official version, the official version shall govern.
>
> The limited permissions granted above are perpetual and will not be revoked by
> Ecma International or its successors or assigns.
>
> This document and the information contained herein is provided on an "AS IS"
> basis and ECMA INTERNATIONAL DISCLAIMS ALL WARRANTIES, EXPRESS OR IMPLIED,
> INCLUDING BUT NOT LIMITED TO ANY WARRANTY THAT THE USE OF THE INFORMATION HEREIN
> WILL NOT INFRINGE ANY OWNERSHIP RIGHTS OR ANY IMPLIED WARRANTIES OF
> MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE.

The schema files themselves are unmodified.
