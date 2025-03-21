"""
snapgene reader main file
SnapGene Reader is an open-source software originally written by Isaac Luo at the Cai Lab.

----------------------------------------
Modified by: CHU Pan
Date: 2025-03-16
Mail: pan_chu@outlook.com

----------------------------------------
This file is a modified version of the original SnapGene Reader.
The original version is available at IsaacLuo/SnapGeneFileReader


Change Log:
    1. Improve the function to read the history of the SnapGene file. After V5.0 if dna file
      the history tree is stored in a compressed format.
    2. Add the function to read the primers of the SnapGene file.
    3. Improve the function to read the features of the SnapGene file.

"""
import struct

# import json
import xmltodict
import lzma
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

try:
    # Biopython <1.78
    from Bio.Alphabet import DNAAlphabet

    has_dna_alphabet = True
except ImportError:
    # Biopython >=1.78
    has_dna_alphabet = False
from Bio.SeqFeature import SeqFeature, FeatureLocation
import html2text

HTML_PARSER = html2text.HTML2Text()
HTML_PARSER.ignore_emphasis = True
HTML_PARSER.ignore_links = True
HTML_PARSER.body_width = 0
HTML_PARSER.single_line_break = True


def parse(val):
    """Parse html."""
    if isinstance(val, str):
        return HTML_PARSER.handle(val).strip().replace("\n", " ").replace('"', "'")
    else:
        return val


def parse_dict(obj):
    """Parse dict in the obj."""
    if isinstance(obj, dict):
        for key in obj:
            if isinstance(obj[key], str):
                obj[key] = parse(obj[key])
            elif isinstance(obj[key], dict):
                parse_dict(obj[key])
    return obj


def remove_suffix(name: str):
    suffix_tag = ['dna', 'gb']
    name = name.replace(' ', '')
    splted_name = name.split('.')
    if splted_name[-1] in suffix_tag:
        return '.'.join(splted_name[:-1])
    else:
        return name


def snapgene_file_to_dict(filepath=None, fileobject=None):
    """Return a dictionary containing the data from a ``*.dna`` file.
    `*.dna` file is a kind of TLV-like packet. 1 byte for the type of the data recorded, 
    4 bytes for the size of the data, and followed the data itself.

    Parameters
    ----------
    filepath
        Path to a .dna file created with SnapGene.

    fileobject
        On object-like pointing to the data of a .dna file created with
        SnapGene.

    Return
    -------
    data: dict
        A dictionary containing the data from a ``*.dna`` file.
    """
    if filepath is not None:
        fileobject = open(filepath, "rb")

    if fileobject.read(1) != b"\t":
        raise ValueError("Wrong format for a SnapGene file!")

    def unpack(size, mode):
        """Unpack the fileobject."""
        return struct.unpack(">" + mode, fileobject.read(size))[0]

    # READ THE DOCUMENT PROPERTIES
    length = unpack(4, "I")
    title = fileobject.read(8).decode("ascii")
    if length != 14 or title != "SnapGene":
        raise ValueError("Wrong format for a SnapGene file !")

    data = dict(
        isDNA=unpack(2, "H"),
        exportVersion=unpack(2, "H"),
        importVersion=unpack(2, "H"),
        features=[],
    )

    while True:
        # READ THE WHOLE FILE, BLOCK BY BLOCK, UNTIL THE END
        next_byte = fileobject.read(1)

        # next_byte table
        # 0: dna sequence
        # 1: compressed DNA
        # 2: unknown
        # 3: unknown
        # 5: primers
        # 6: notes
        # 7: history tree
        # 8: additional sequence properties segment
        # 9: file Description
        # 10: features
        # 11: history node
        # 13: unknown
        # 16: alignable sequence
        # 17: alignable sequence
        # 18: sequence trace
        # 19: Uracil Positions
        # 20: custom DNA colors

        if next_byte == b"":
            # END OF FILE
            break
        block_size = unpack(4, "I")
        # check the reading progress
        # print(f"block_size: {block_size}", f"next_byte: {next_byte}")
        if ord(next_byte) == 0:
            # READ THE SEQUENCE AND ITS PROPERTIES
            props = unpack(1, "b")
            data["dna"] = dict(
                topology="circular" if props & 0x01 else "linear",
                strandedness="double" if props & 0x02 > 0 else "single",
                damMethylated=props & 0x04 > 0,
                dcmMethylated=props & 0x08 > 0,
                ecoKIMethylated=props & 0x10 > 0,
                length=block_size - 1,
            )
            data["seq"] = fileobject.read(block_size - 1).decode("ascii")
        elif ord(next_byte) == 5:
            # READ THE PRIMERS
            """
            Example for primers:
            <Primer recentID="0" name="rbna_51" sequence="gctagcaacgcaatgacgTTATATCGTATGGGGCTGACTTCAGGTG" description="&quot;tm:60, binding at p15A&quot;" dateAdded="2020-04-02T06:06:12Z">
            <BindingSite location="724-751" boundStrand="1" annealedBases="TTATATCGTATGGGGCTGACTTCAGGTG" meltingTemperature="60">
            <Component bases="gctagcaacgcaatgacg"/>
            <Component hybridizedRange="724-751" bases="TTATATCGTATGGGGCTGACTTCAGGTG"/>
            </BindingSite>
            <BindingSite simplified="1" location="724-751" boundStrand="1" annealedBases="TTATATCGTATGGGGCTGACTTCAGGTG" meltingTemperature="60">
            <Component bases="gctagcaacgcaatgacg"/><Component hybridizedRange="724-751" bases="TTATATCGTATGGGGCTGACTTCAGGTG"/>
            </BindingSite>
            </Primer>
            """
            primers_data = xmltodict.parse(fileobject.read(block_size))
            primers = primers_data["Primers"]["Primer"]
            data["primers"] = []
            if not isinstance(primers, list):
                primers = [primers]
            for primer in primers:
                primer_dict = {}
                primer_dict['name'] = primer["@name"]
                primer_dict['sequence'] = primer["@sequence"]
                try:
                    primer_dict['description'] = primer["@description"]

                except KeyError:
                    pass
                    
                data["primers"].append(primer_dict)

            # data["primers"] = primers
        elif ord(next_byte) == 6:
            # READ THE NOTES
            block_content = fileobject.read(block_size).decode("utf-8")
            note_data = parse_dict(xmltodict.parse(block_content))
            data["notes"] = note_data["Notes"]        
        elif ord(next_byte) == 7:
            # read history
            hist_content = fileobject.read(block_size)
            try:
                hist2xml = hist_content.decode("utf-8")
                
            except Exception as e:
                #　try to read the history decompress via LZMA
                hist_content_compressed = hist_content
                try:
                    hist2xml = lzma.decompress(hist_content_compressed).decode("utf-8")
                except Exception as e:
                    continue

            hist_data = parse_dict(xmltodict.parse(hist2xml))

            asb_frags = hist_data['HistoryTree']['Node']['Node']
            asb_frags_num = len(asb_frags)
            asb_info_dic = dict(name=remove_suffix(hist_data['HistoryTree']['Node']['@name']),
                                length=hist_data['HistoryTree']['Node']['@seqLen'],
                                operation=hist_data['HistoryTree']['Node']['@operation'],
                                fragments_number=asb_frags_num)
            for frag_i, frag in enumerate(asb_frags):
                # print(filepath)
                frag_dic = dict(name=remove_suffix(frag['@name']),
                                length=frag['@seqLen']
                                )
                try:
                    frag_dic['operation'] = frag['@operation']
                except KeyError:
                    pass
                try:
                    if frag['Oligo']:
                        frag_info = frag['Node']
                        amplify_primers = frag_info['Primers']['Primer']
                        for index, primer in enumerate(amplify_primers):
                            primer_dict = amplify_primers[index]
                            frag_dic[f'primers_{index}'] = dict(name=remove_suffix(primer_dict['@name']),
                                                                melting_temp=primer_dict['BindingSite'][
                                                                    '@meltingTemperature'],
                                                                sequence=primer_dict['@sequence'])
                        frag_dic['template'] = remove_suffix(remove_suffix(frag_info['@name']))
                except KeyError:
                    frag_dic['template'] = '-'
                asb_info_dic[f'fragment_{frag_i}'] = frag_dic
                data['history'] = asb_info_dic
        elif ord(next_byte) == 10:
            # READ THE FEATURES
            strand_dict = {"0": ".", "1": "+", "2": "-", "3": "="}
            format_dict = {"@text": parse, "@int": int}
            features_data = xmltodict.parse(fileobject.read(block_size))
            features = features_data["Features"]["Feature"]
            if not isinstance(features, list):
                features = [features]
            for feature in features:
                segments = feature["Segment"]
                if not isinstance(segments, list):
                    segments = [segments]
                segments_ranges = [
                    sorted([int(e) for e in segment["@range"].split("-")])
                    for segment in segments
                ]
                qualifiers = feature.get("Q", [])
                if not isinstance(qualifiers, list):
                    qualifiers = [qualifiers]
                parsed_qualifiers = {}
                for qualifier in qualifiers:
                    if qualifier["V"] is None:
                        pass
                    elif isinstance(qualifier["V"], list):
                        if len(qualifier["V"][0].items()) == 1:
                            parsed_qualifiers[qualifier["@name"]] = l_v = []
                            for e_v in qualifier["V"]:
                                fmt, value = e_v.popitem()
                                fmt = format_dict.get(fmt, parse)
                                l_v.append(fmt(value))
                        else:
                            parsed_qualifiers[qualifier["@name"]] = d_v = {}
                            for e_v in qualifier["V"]:
                                # hwo much items in the dict?
                                if len(e_v.items()) == 1:
                                    fmt, value = e_v.popitem()
                                    fmt = format_dict.get(fmt, parse)
                                    d_v[value] = fmt(value)
                                elif len(e_v.items()) == 2:
                                    (fmt1, value1), (_, value2) = e_v.items()
                                    fmt = format_dict.get(fmt1, parse)
                                    d_v[value2] = fmt(value1)
                                elif len(e_v.items()) == 3:
                                    (fmt1, value1), (_, value2), (_, value3) = e_v.items()
                                    fmt = format_dict.get(fmt1, parse)
                                    d_v[value2] = fmt(value1)
                                    d_v[value3] = fmt(value1)
                                # (fmt1, value1), (_, value2) = e_v.items()
                                # fmt = format_dict.get(fmt1, parse)
                                # d_v[value2] = fmt(value1)
                    else:
                        fmt, value = qualifier["V"].popitem()
                        fmt = format_dict.get(fmt, parse)
                        parsed_qualifiers[qualifier["@name"]] = fmt(value)

                if "label" not in parsed_qualifiers:
                    parsed_qualifiers["label"] = feature["@name"]
                if "note" not in parsed_qualifiers:
                    parsed_qualifiers["note"] = []
                if not isinstance(parsed_qualifiers["note"], list):
                    parsed_qualifiers["note"] = [parsed_qualifiers["note"]]
                color = segments[0]["@color"]
                parsed_qualifiers["note"].append("color: " + color)

                data["features"].append(
                    dict(
                        start=min([start - 1 for (start, end) in segments_ranges]),
                        end=max([end for (start, end) in segments_ranges]),
                        strand=strand_dict[feature.get("@directionality", "0")],
                        type=feature["@type"],
                        name=feature["@name"],
                        color=segments[0]["@color"],
                        textColor="black",
                        segments=segments,
                        row=0,
                        isOrf=False,
                        qualifiers=parsed_qualifiers,
                    )
                )
        else:
            # WE IGNORE THE WHOLE BLOCK
            fileobject.read(block_size)
            pass

    fileobject.close()
    return data


def snapgene_file_to_seqrecord(filepath=None, fileobject=None):
    """Return a BioPython SeqRecord from the data of a ``*.dna`` file.

    Parameters
    ----------
    filepath
        Path to a .dna file created with SnapGene.

    fileobject
        On object-like pointing to the data of a .dna file created with
        SnapGene.
    """
    data = snapgene_file_to_dict(filepath=filepath, fileobject=fileobject)
    strand_dict = {"+": 1, "-": -1, ".": 0}

    if has_dna_alphabet:
        seq = Seq(data["seq"], alphabet=DNAAlphabet())
    else:
        seq = Seq(data["seq"])

    seqrecord = SeqRecord(
        seq=seq,
        features=[
            SeqFeature(
                location=FeatureLocation(
                    start=feature["start"],
                    end=feature["end"],
                    strand=strand_dict[feature["strand"]],
                ),
                strand=strand_dict[feature["strand"]],
                type=feature["type"],
                qualifiers=feature["qualifiers"],
            )
            for feature in data["features"]
        ],
        annotations=dict(topology=data["dna"]["topology"], **data["notes"]),
    )

    seqrecord.annotations["molecule_type"] = "DNA"

    return seqrecord


def snapgene_file_to_gbk(read_file_object, write_file_object):
    """Convert a file object."""

    def analyse_gs(dic, *args, **kwargs):
        """Extract gs block in the document."""
        if "default" not in kwargs:
            kwargs["default"] = None

        for arg in args:
            if arg in dic:
                dic = dic[arg]
            else:
                return kwargs["default"]
        return dic

    data = snapgene_file_to_dict(fileobject=read_file_object)
    wfo = write_file_object
    wfo.write(
        (
            "LOCUS       Exported              {0:>6} bp ds-DNA     {1:>8} SYN \
15-APR-2012\n"
        ).format(len(data["seq"]), data["dna"]["topology"])
    )
    definition = analyse_gs(data, "notes", "Description", default=".").replace(
        "\n", "\n            "
    )
    wfo.write("DEFINITION  {}\n".format(definition))
    wfo.write("ACCESSION   .\n")
    wfo.write("VERSION     .\n")
    wfo.write(
        "KEYWORDS    {}\n".format(
            analyse_gs(data, "notes", "CustomMapLabel", default=".")
        )
    )
    wfo.write("SOURCE      .\n")
    wfo.write("  ORGANISM  .\n")

    references = analyse_gs(data, "notes", "References")

    reference_count = 0
    if references:
        for key in references:
            reference_count += 1
            ref = references[key]
            wfo.write(
                "REFERENCE   {}  (bases 1 to {} )\n".format(
                    reference_count, analyse_gs(data, "dna", "length")
                )
            )
            for key2 in ref:
                gb_key = key2.replace("@", "").upper()
                wfo.write("  {}   {}\n".format(gb_key, ref[key2]))

    # generate special reference
    reference_count += 1
    wfo.write(
        "REFERENCE   {}  (bases 1 to {} )\n".format(
            reference_count, analyse_gs(data, "dna", "length")
        )
    )
    wfo.write("  AUTHORS   SnapGeneReader\n")
    wfo.write("  TITLE     Direct Submission\n")
    wfo.write(
        (
            "  JOURNAL   Exported Monday, Sep 05, 2020 from SnapGene File\
 Reader\n"
        )
    )
    wfo.write(
        "            https://github.com/Edinburgh-Genome-Foundry/SnapGeneReader\n"
    )

    wfo.write(
        "COMMENT     {}\n".format(
            analyse_gs(data, "notes", "Comments", default=".")
            .replace("\n", "\n            ")
            .replace("\\", "")
        )
    )
    wfo.write("FEATURES             Location/Qualifiers\n")

    features = analyse_gs(data, "features")
    for feature in features:
        strand = analyse_gs(feature, "strand", default="")

        segments = analyse_gs(feature, "segments", default=[])
        segments = [x for x in segments if x["@type"] == "standard"]
        if len(segments) > 1:
            line = "join("
            for segment in segments:
                segment_range = analyse_gs(segment, "@range").replace("-", "..")
                if analyse_gs(segment, "@type") == "standard":
                    line += segment_range
                    line += ","
            line = line[:-1] + ")"
        else:
            line = "{}..{}".format(
                analyse_gs(feature, "start", default=" "),
                analyse_gs(feature, "end", default=" "),
            )

        if strand == "-":
            wfo.write(
                "     {} complement({})\n".format(
                    analyse_gs(feature, "type", default=" ").ljust(15), line,
                )
            )
        else:
            wfo.write(
                "     {} {}\n".format(
                    analyse_gs(feature, "type", default=" ").ljust(15), line,
                )
            )
        strand = analyse_gs(feature, "strand", default="")
        # if strand == '-':
        #     wfo.write('                     /direction=LEFT\n')
        # name
        wfo.write(
            '                     /note="{}"\n'.format(
                analyse_gs(feature, "name", default="feature")
            )
        )
        # qualifiers
        for q_key in analyse_gs(feature, "qualifiers", default={}):
            # do not write label, because it has been written at first.
            if q_key == "label":
                pass
            elif q_key == "note":
                for note in analyse_gs(feature, "qualifiers", q_key, default=[]):
                    # do note write color, because it will be written later
                    if note[:6] != "color:":
                        wfo.write('                     /note="{}"\n'.format(note))
            else:
                wfo.write(
                    '                     /{}="{}"\n'.format(
                        q_key, analyse_gs(feature, "qualifiers", q_key, default="")
                    )
                )
        if len(segments) > 1:
            wfo.write(
                (
                    '                     /note="This feature \
has {} segments:'
                ).format(len(segments))
            )
            for seg_i, seg in enumerate(segments):
                segment_name = analyse_gs(seg, "@name", default="")
                if segment_name:
                    segment_name = " / {}".format(segment_name)
                wfo.write(
                    "\n                        {}:  {} / {}{}".format(
                        seg_i,
                        seg["@range"].replace("-", " .. "),
                        seg["@color"],
                        segment_name,
                    )
                )
            wfo.write('"\n')
        else:
            # write colors and direction
            wfo.write(
                21 * " "
                + '/note="color: {}'.format(
                    analyse_gs(feature, "color", default="#ffffff")
                )
            )
            if strand == "-":
                wfo.write('; direction: LEFT"\n')
                # wfo.write('"\n')
            elif strand == "+":
                wfo.write('; direction: RIGHT"\n')
            else:
                wfo.write('"\n')

    # sequence
    wfo.write("ORIGIN\n")
    seq = analyse_gs(data, "seq")
    # divide rows
    for i in range(0, len(seq), 60):
        wfo.write(str(i).rjust(9))
        for j in range(i, min(i + 60, len(seq)), 10):
            wfo.write(" {}".format(seq[j : j + 10]))
        wfo.write("\n")
    wfo.write("//\n")


if __name__ == "__main__":
    pass
