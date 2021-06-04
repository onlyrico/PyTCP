#!/usr/bin/env python3

############################################################################
#                                                                          #
#  PyTCP - Python TCP/IP stack                                             #
#  Copyright (C) 2020-2021  Sebastian Majewski                             #
#                                                                          #
#  This program is free software: you can redistribute it and/or modify    #
#  it under the terms of the GNU General Public License as published by    #
#  the Free Software Foundation, either version 3 of the License, or       #
#  (at your option) any later version.                                     #
#                                                                          #
#  This program is distributed in the hope that it will be useful,         #
#  but WITHOUT ANY WARRANTY; without even the implied warranty of          #
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the           #
#  GNU General Public License for more details.                            #
#                                                                          #
#  You should have received a copy of the GNU General Public License       #
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.  #
#                                                                          #
#  Author's email: ccie18643@gmail.com                                     #
#  Github repository: https://github.com/ccie18643/PyTCP                   #
#                                                                          #
############################################################################


#
# icmp6/fpp.py - Fast Packet Parse support class for ICMPv6 protocol
#


from __future__ import annotations  # Required by Python ver < 3.10

import struct
from typing import TYPE_CHECKING, Optional

import config
import icmp6.ps
from lib.ip6_address import Ip6Address, Ip6Mask, Ip6Network
from lib.mac_address import MacAddress
from misc.ip_helper import inet_cksum

if TYPE_CHECKING:
    from misc.packet import PacketRx


class Icmp6Parser:
    """ICMPv6 packet parser class"""

    def __init__(self, packet_rx: PacketRx) -> None:
        """Class constructor"""

        assert packet_rx.ip6 is not None

        packet_rx.icmp6 = self

        self._frame = packet_rx.frame
        self._plen = packet_rx.ip6.dlen

        packet_rx.parse_failed = self._packet_integrity_check(packet_rx.ip6.pshdr_sum) or self._packet_sanity_check(
            packet_rx.ip6.src, packet_rx.ip6.dst, packet_rx.ip6.hop
        )

    def __len__(self) -> int:
        """Number of bytes remaining in the frame"""

        return len(self._frame)

    def __str__(self) -> str:
        """Packet log string"""

        log = f"ICMPv6 type {self.type}, code {self.code}"

        if self.type == icmp6.ps.ICMP6_UNREACHABLE:
            pass

        elif self.type == icmp6.ps.ICMP6_ECHOR_REQUEST:
            log += f", id {self.ec_id}, seq {self.ec_seq}"

        elif self.type == icmp6.ps.ICMP6_ECHOR_REPLY:
            log += f", id {self.ec_id}, seq {self.ec_seq}"

        elif self.type == icmp6.ps.ICMP6_ROUTER_SOLICITATION:
            assert self.nd_options is not None
            for nd_option in self.nd_options:
                log += ", " + str(nd_option)

        elif self.type == icmp6.ps.ICMP6_ROUTER_ADVERTISEMENT:
            assert self.nd_options is not None
            log += f", hop {self.ra_hop}"
            log += f", flags {'M' if self.ra_flag_m else '-'}{'O' if self.ra_flag_o else '-'}"
            log += f", rlft {self.ra_router_lifetime}, reacht {self.ra_reachable_time}, retrt {self.ra_retrans_timer}"
            for nd_option in self.nd_options:
                log += ", " + str(nd_option)

        elif self.type == icmp6.ps.ICMP6_NEIGHBOR_SOLICITATION:
            assert self.nd_options is not None
            log += f", target {self.ns_target_address}"
            for nd_option in self.nd_options:
                log += ", " + str(nd_option)

        elif self.type == icmp6.ps.ICMP6_NEIGHBOR_ADVERTISEMENT:
            assert self.nd_options is not None
            log += f", target {self.na_target_address}"
            log += f", flags {'R' if self.na_flag_r else '-'}{'S' if self.na_flag_s else '-'}{'O' if self.na_flag_o else '-'}"
            for nd_option in self.nd_options:
                log += ", " + str(nd_option)

        elif self.type == icmp6.ps.ICMP6_MLD2_REPORT:
            pass

        return log

    @property
    def type(self) -> int:
        """Read 'Type' field"""

        return self._frame[0]

    @property
    def code(self) -> int:
        """Read 'Code' field"""

        return self._frame[1]

    @property
    def cksum(self) -> int:
        """Read 'Checksum' field"""

        if "_cache__cksum" not in self.__dict__:
            self._cache__cksum: int = struct.unpack("!H", self._frame[2:4])[0]
        return self._cache__cksum

    @property
    def un_data(self) -> bytes:
        """Read data carried by Unreachable message"""

        if "_cache__un_data" not in self.__dict__:
            assert self.type == icmp6.ps.ICMP6_UNREACHABLE
            self._cache__un_data = self._frame[8 : self.plen]
        return self._cache__un_data

    @property
    def ec_id(self) -> int:
        """Read Echo 'Id' field"""

        if "_cache__ec_id" not in self.__dict__:
            assert self.type in {icmp6.ps.ICMP6_ECHOR_REQUEST, icmp6.ps.ICMP6_ECHOR_REPLY}
            self._cache__ec_id: int = struct.unpack("!H", self._frame[4:6])[0]
        return self._cache__ec_id

    @property
    def ec_seq(self) -> int:
        """Read Echo 'Seq' field"""

        if "_cache__ec_seq" not in self.__dict__:
            assert self.type in {icmp6.ps.ICMP6_ECHOR_REQUEST, icmp6.ps.ICMP6_ECHOR_REPLY}
            self._cache__ec_seq: int = struct.unpack("!H", self._frame[6:8])[0]
        return self._cache__ec_seq

    @property
    def ec_data(self) -> bytes:
        """Read data carried by Echo message"""

        if "_cache__ec_data" not in self.__dict__:
            assert self.type in {icmp6.ps.ICMP6_ECHOR_REQUEST, icmp6.ps.ICMP6_ECHOR_REPLY}
            self._cache__ec_data = self._frame[8 : self.plen]
        return self._cache__ec_data

    @property
    def ra_hop(self) -> int:
        """Read ND RA 'Hop limit' field"""

        assert self.type == icmp6.ps.ICMP6_ROUTER_ADVERTISEMENT
        return self._frame[4]

    @property
    def ra_flag_m(self) -> bool:
        """Read ND RA 'M flag' field"""

        if "_cache__ra_flag_m" not in self.__dict__:
            assert self.type == icmp6.ps.ICMP6_ROUTER_ADVERTISEMENT
            self._cache__ra_flag_m = bool(self._frame[5] & 0b10000000)
        return self._cache__ra_flag_m

    @property
    def ra_flag_o(self) -> bool:
        """Read ND RA 'O flag' field"""

        if "_cache__ra_flag_o" not in self.__dict__:
            assert self.type == icmp6.ps.ICMP6_ROUTER_ADVERTISEMENT
            self._cache__ra_flag_o = bool(self._frame[5] & 0b01000000)
        return self._cache__ra_flag_o

    @property
    def ra_router_lifetime(self) -> int:
        """Read ND RA 'Router lifetime' field"""

        if "_cache__ra_router_lifetime" not in self.__dict__:
            assert self.type == icmp6.ps.ICMP6_ROUTER_ADVERTISEMENT
            self._cache__ra_router_lifetime: int = struct.unpack("!H", self._frame[6:8])[0]
        return self._cache__ra_router_lifetime

    @property
    def ra_reachable_time(self) -> int:
        """Read ND RA 'Reachable time' field"""

        if "_cache__ra_reachable_time" not in self.__dict__:
            assert self.type == icmp6.ps.ICMP6_ROUTER_ADVERTISEMENT
            self._cache__ra_reachable_time: int = struct.unpack("!L", self._frame[8:12])[0]
        return self._cache__ra_reachable_time

    @property
    def ra_retrans_timer(self) -> int:
        """Read ND RA 'Retransmision timer' field"""

        if "_cache__ra_retrans_timer" not in self.__dict__:
            assert self.type == icmp6.ps.ICMP6_ROUTER_ADVERTISEMENT
            self._cache__ra_retrans_timer: int = struct.unpack("!L", self._frame[12:16])[0]
        return self._cache__ra_retrans_timer

    @property
    def ns_target_address(self) -> Ip6Address:
        """Read ND NS 'Target adress' field"""

        if "_cache__ns_target_address" not in self.__dict__:
            assert self.type == icmp6.ps.ICMP6_NEIGHBOR_SOLICITATION
            self._cache__ns_target_address = Ip6Address(self._frame[8:24])
        return self._cache__ns_target_address

    @property
    def na_flag_r(self) -> bool:
        """Read ND NA 'R flag' field"""

        if "_cache__na_flag_r" not in self.__dict__:
            assert self.type == icmp6.ps.ICMP6_NEIGHBOR_ADVERTISEMENT
            self._cache__na_flag_r = bool(self._frame[4] & 0b10000000)
        return self._cache__na_flag_r

    @property
    def na_flag_s(self) -> bool:
        """Read ND NA 'S flag' field"""

        if "_cache__na_flag_s" not in self.__dict__:
            assert self.type == icmp6.ps.ICMP6_NEIGHBOR_ADVERTISEMENT
            self._cache__na_flag_s = bool(self._frame[4] & 0b01000000)
        return self._cache__na_flag_s

    @property
    def na_flag_o(self) -> bool:
        """Read ND NA 'O flag' field"""

        if "_cache__na_flag_o" not in self.__dict__:
            assert self.type == icmp6.ps.ICMP6_NEIGHBOR_ADVERTISEMENT
            self._cache__na_flag_o = bool(self._frame[4] & 0b00100000)
        return self._cache__na_flag_o

    @property
    def na_target_address(self) -> Ip6Address:
        """Read ND NA 'Taret address' field"""

        if "_cache__na_target_address" not in self.__dict__:
            assert self.type == icmp6.ps.ICMP6_NEIGHBOR_ADVERTISEMENT
            self._cache__na_target_address = Ip6Address(self._frame[8:24])
        return self._cache__na_target_address

    @property
    def mld2_rep_nor(self) -> int:
        """Read ICMP6_MLD2 Report 'Number of multicast address records' field"""

        if "_cache__mld2_rep_nor" not in self.__dict__:
            assert self.type == icmp6.ps.ICMP6_MLD2_REPORT
            self._cache__mld2_rep_nor: int = struct.unpack("!H", self._frame[6:8])[0]
        return self._cache__mld2_rep_nor

    @property
    def mld2_rep_records(self) -> list[MulticastAddressRecord]:
        """Read ICMP6_MLD2 Report record list"""

        if "_cache__mld2_rep_records" not in self.__dict__:
            assert self.type == icmp6.ps.ICMP6_MLD2_REPORT
            self._cache__mld2_rep_records = []
            raw_records = self._frame[8:]
            for _ in range(self.mld2_rep_nor):
                record = MulticastAddressRecord(raw_records)
                raw_records = raw_records[len(record) :]
                self._cache__mld2_rep_records.append(record)
        return self._cache__mld2_rep_records

    def _read_nd_options(self, optr: int) -> list[Icmp6NdOptSLLA | Icmp6NdOptTLLA | Icmp6NdOptPI | Icmp6NdOptUnk]:
        """Read ND options"""

        nd_options: list = []
        while optr < len(self._frame):
            nd_options.append(
                {icmp6.ps.ICMP6_ND_OPT_SLLA: Icmp6NdOptSLLA, icmp6.ps.ICMP6_ND_OPT_TLLA: Icmp6NdOptTLLA, icmp6.ps.ICMP6_ND_OPT_PI: Icmp6NdOptPI}.get(
                    self._frame[optr], Icmp6NdOptUnk
                )(self._frame[optr:])
            )
            optr += self._frame[optr + 1] << 3

        return nd_options

    @property
    def nd_options(self) -> list[Icmp6NdOptSLLA | Icmp6NdOptTLLA | Icmp6NdOptPI | Icmp6NdOptUnk]:
        """Read ND options"""

        if "_cache__nd_options" not in self.__dict__:
            assert self.type in {
                icmp6.ps.ICMP6_ROUTER_SOLICITATION,
                icmp6.ps.ICMP6_ROUTER_ADVERTISEMENT,
                icmp6.ps.ICMP6_NEIGHBOR_SOLICITATION,
                icmp6.ps.ICMP6_NEIGHBOR_ADVERTISEMENT,
            }
            optr = {
                icmp6.ps.ICMP6_ROUTER_SOLICITATION: 12,
                icmp6.ps.ICMP6_ROUTER_ADVERTISEMENT: 16,
                icmp6.ps.ICMP6_NEIGHBOR_SOLICITATION: 24,
                icmp6.ps.ICMP6_NEIGHBOR_ADVERTISEMENT: 24,
            }[self.type]
            self._cache__nd_options = self._read_nd_options(optr)
        return self._cache__nd_options

    @property
    def nd_opt_slla(self) -> Optional[MacAddress]:
        """ICMPv6 ND option - Source Link Layer Address (1)"""

        if "_cache__nd_opt_slla" not in self.__dict__:
            assert self.type in {
                icmp6.ps.ICMP6_ROUTER_SOLICITATION,
                icmp6.ps.ICMP6_ROUTER_ADVERTISEMENT,
                icmp6.ps.ICMP6_NEIGHBOR_SOLICITATION,
                icmp6.ps.ICMP6_NEIGHBOR_ADVERTISEMENT,
            }
            for option in self.nd_options:
                if isinstance(option, Icmp6NdOptSLLA):
                    self._cache__nd_opt_slla: Optional[MacAddress] = option.slla
                    break
            else:
                self._cache__nd_opt_slla = None
        return self._cache__nd_opt_slla

    @property
    def nd_opt_tlla(self) -> Optional[MacAddress]:
        """ICMPv6 ND option - Target Link Layer Address (2)"""

        if "_cache__nd_opt_tlla" not in self.__dict__:
            assert self.type in {
                icmp6.ps.ICMP6_ROUTER_SOLICITATION,
                icmp6.ps.ICMP6_ROUTER_ADVERTISEMENT,
                icmp6.ps.ICMP6_NEIGHBOR_SOLICITATION,
                icmp6.ps.ICMP6_NEIGHBOR_ADVERTISEMENT,
            }
            for option in self.nd_options:
                if isinstance(option, Icmp6NdOptTLLA):
                    self._cache__nd_opt_tlla: Optional[MacAddress] = option.tlla
                    break
            else:
                self._cache__nd_opt_tlla = None
        return self._cache__nd_opt_tlla

    @property
    def nd_opt_pi(self) -> list[Ip6Network]:
        """ICMPv6 ND option - Prefix Info (3) - Returns list of prefixes that can be used for address autoconfiguration"""

        if "_cache__nd_opt_pi" not in self.__dict__:
            assert self.type in {
                icmp6.ps.ICMP6_ROUTER_SOLICITATION,
                icmp6.ps.ICMP6_ROUTER_ADVERTISEMENT,
                icmp6.ps.ICMP6_NEIGHBOR_SOLICITATION,
                icmp6.ps.ICMP6_NEIGHBOR_ADVERTISEMENT,
            }
            self._cache__nd_opt_pi = [_.prefix for _ in self.nd_options if isinstance(_, Icmp6NdOptPI) and _.flag_a and len(_.prefix.mask) == 64]
        return self._cache__nd_opt_pi

    @property
    def plen(self) -> int:
        """Calculate packet length"""

        return self._plen

    @property
    def packet_copy(self) -> bytes:
        """Read the whole packet"""

        if "_cache__packet_copy" not in self.__dict__:
            self._cache__packet_copy = self._frame[: self.plen]
        return self._cache__packet_copy

    def _nd_option_integrity_check(self, optr: int) -> str:
        """Check integrity of ICMPv6 ND options"""

        while optr < len(self._frame):
            if optr + 1 > len(self._frame):
                return "ICMPv6 sanity check fail - wrong option length (I)"
            if self._frame[optr + 1] == 0:
                return "ICMPv6 sanity check fail - wrong option length (II)"
            optr += self._frame[optr + 1] << 3
            if optr > len(self._frame):
                return "ICMPv6 sanity check fail - wrong option length (III)"

        return ""

    def _packet_integrity_check(self, pshdr_sum: int) -> str:
        """Packet integrity check to be run on raw frame prior to parsing to make sure parsing is safe"""

        if not config.packet_integrity_check:
            return ""

        if inet_cksum(self._frame[: self._plen], pshdr_sum):
            return "ICMPv6 integrity - wrong packet checksum"

        if not icmp6.ps.ICMP6_HEADER_LEN <= self._plen <= len(self):
            return "ICMPv6 integrity - wrong packet length (I)"

        if self._frame[0] == icmp6.ps.ICMP6_UNREACHABLE:
            if not 12 <= self._plen <= len(self):
                return "ICMPv6 integrity - wrong packet length (II)"

        elif self._frame[0] in {icmp6.ps.ICMP6_ECHOR_REQUEST, icmp6.ps.ICMP6_ECHOR_REPLY}:
            if not 8 <= self._plen <= len(self):
                return "ICMPv6 integrity - wrong packet length (II)"

        elif self._frame[0] == icmp6.ps.ICMP6_MLD2_QUERY:
            if not 28 <= self._plen <= len(self):
                return "ICMPv6 integrity - wrong packet length (II)"
            if self._plen != 28 + struct.unpack("!H", self._frame[26:28])[0] * 16:
                return "ICMPv6 integrity - wrong packet length (III)"

        elif self._frame[0] == icmp6.ps.ICMP6_ROUTER_SOLICITATION:
            if not 8 <= self._plen <= len(self):
                return "ICMPv6 integrity - wrong packet length (II)"
            if fail := self._nd_option_integrity_check(8):
                return fail

        elif self._frame[0] == icmp6.ps.ICMP6_ROUTER_ADVERTISEMENT:
            if not 16 <= self._plen <= len(self):
                return "ICMPv6 integrity - wrong packet length (II)"
            if fail := self._nd_option_integrity_check(16):
                return fail

        elif self._frame[0] == icmp6.ps.ICMP6_NEIGHBOR_SOLICITATION:
            if not 24 <= self._plen <= len(self):
                return "ICMPv6 integrity - wrong packet length (II)"
            if fail := self._nd_option_integrity_check(24):
                return fail

        elif self._frame[0] == icmp6.ps.ICMP6_NEIGHBOR_ADVERTISEMENT:
            if not 24 <= self._plen <= len(self):
                return "ICMPv6 integrity - wrong packet length (II)"
            if fail := self._nd_option_integrity_check(24):
                return fail

        elif self._frame[0] == icmp6.ps.ICMP6_MLD2_REPORT:
            if not 8 <= self._plen <= len(self):
                return "ICMPv6 integrity - wrong packet length (II)"
            optr = 8
            for _ in range(struct.unpack("!H", self._frame[6:8])[0]):
                if optr + 20 > self._plen:
                    return "ICMPv6 integrity - wrong packet length (III)"
                optr += 20 + self._frame[optr + 1] + struct.unpack_from("! H", self._frame, optr + 2)[0] * 16
            if optr != self._plen:
                return "ICMPv6 integrity - wrong packet length (IV)"

        return ""

    def _packet_sanity_check(self, ip6_src: Ip6Address, ip6_dst: Ip6Address, ip6_hop: int) -> str:
        """Packet sanity check to be run on parsed packet to make sure frame's fields contain sane values"""

        if not config.packet_sanity_check:
            return ""

        if self.type == icmp6.ps.ICMP6_UNREACHABLE:
            if self.code not in {0, 1, 2, 3, 4, 5, 6}:
                return "ICMPv6 sanity - 'code' must be [0-6] (RFC 4861)"

        elif self.type == icmp6.ps.ICMP6_PACKET_TOO_BIG:
            if not self.code == 0:
                return "ICMPv6 sanity - 'code' should be 0 (RFC 4861)"

        elif self.type == icmp6.ps.ICMP6_TIME_EXCEEDED:
            if self.code not in {0, 1}:
                return "ICMPv6 sanity - 'code' must be [0-1] (RFC 4861)"

        elif self.type == icmp6.ps.ICMP6_PARAMETER_PROBLEM:
            if self.code not in {0, 1, 2}:
                return "ICMPv6 sanity - 'code' must be [0-2] (RFC 4861)"

        elif self.type in {icmp6.ps.ICMP6_ECHOR_REQUEST, icmp6.ps.ICMP6_ECHOR_REPLY}:
            if not self.code == 0:
                return "ICMPv6 sanity - 'code' should be 0 (RFC 4861)"

        elif self.type == icmp6.ps.ICMP6_MLD2_QUERY:
            if not self.code == 0:
                return "ICMPv6 sanity - 'code' must be 0 (RFC 3810)"
            if not ip6_hop == 1:
                return "ICMPv6 sanity - 'hop' must be 255 (RFC 3810)"

        elif self.type == icmp6.ps.ICMP6_ROUTER_SOLICITATION:
            if not self.code == 0:
                return "ICMPv6 sanity - 'code' must be 0 (RFC 4861)"
            if not ip6_hop == 255:
                return "ICMPv6 sanity - 'hop' must be 255 (RFC 4861)"
            if not (ip6_src.is_unicast or ip6_src.is_unspecified):
                return "ICMPv6 sanity - 'src' must be unicast or unspecified (RFC 4861)"
            if not ip6_dst == Ip6Address("ff02::2"):
                return "ICMPv6 sanity - 'dst' must be all-routers (RFC 4861)"
            if ip6_src.is_unspecified and self.nd_opt_slla:
                return "ICMPv6 sanity - 'nd_opt_slla' must not be included if 'src' is unspecified (RFC 4861)"

        elif self.type == icmp6.ps.ICMP6_ROUTER_ADVERTISEMENT:
            if not self.code == 0:
                return "ICMPv6 sanity - 'code' must be 0 (RFC 4861)"
            if not ip6_hop == 255:
                return "ICMPv6 sanity - 'hop' must be 255 (RFC 4861)"
            if not ip6_src.is_link_local:
                return "ICMPv6 sanity - 'src' must be link local (RFC 4861)"
            if not (ip6_dst.is_unicast or ip6_dst == Ip6Address("ff02::1")):
                return "ICMPv6 sanity - 'dst' must be unicast or all-nodes (RFC 4861)"

        elif self.type == icmp6.ps.ICMP6_NEIGHBOR_SOLICITATION:
            if not self.code == 0:
                return "ICMPv6 sanity - 'code' must be 0 (RFC 4861)"
            if not ip6_hop == 255:
                return "ICMPv6 sanity - 'hop' must be 255 (RFC 4861)"
            if not (ip6_src.is_unicast or ip6_src.is_unspecified):
                return "ICMPv6 sanity - 'src' must be unicast or unspecified (RFC 4861)"
            if ip6_dst not in {self.ns_target_address, self.ns_target_address.solicited_node_multicast}:
                return "ICMPv6 sanity - 'dst' must be 'ns_target_address' or it's solicited-node multicast (RFC 4861)"
            if not self.ns_target_address.is_unicast:
                return "ICMPv6 sanity - 'ns_target_address' must be unicast (RFC 4861)"
            if ip6_src.is_unspecified and self.nd_opt_slla is not None:
                return "ICMPv6 sanity - 'nd_opt_slla' must not be included if 'src' is unspecified"

        elif self.type == icmp6.ps.ICMP6_NEIGHBOR_ADVERTISEMENT:
            if not self.code == 0:
                return "ICMPv6 sanity - 'code' must be 0 (RFC 4861)"
            if not ip6_hop == 255:
                return "ICMPv6 sanity - 'hop' must be 255 (RFC 4861)"
            if not ip6_src.is_unicast:
                return "ICMPv6 sanity - 'src' must be unicast (RFC 4861)"
            if self.na_flag_s is True and not (ip6_dst.is_unicast or ip6_dst == Ip6Address("ff02::1")):
                return "ICMPv6 sanity - if 'na_flag_s' is set then 'dst' must be unicast or all-nodes (RFC 4861)"
            if self.na_flag_s is False and not ip6_dst == Ip6Address("ff02::1"):
                return "ICMPv6 sanity - if 'na_flag_s' is not set then 'dst' must be all-nodes (RFC 4861)"

        elif self.type == icmp6.ps.ICMP6_MLD2_REPORT:
            if not self.code == 0:
                return "ICMPv6 sanity - 'code' must be 0 (RFC 3810)"
            if not ip6_hop == 1:
                return "ICMPv6 sanity - 'hop' must be 1 (RFC 3810)"

        return ""


#
#   ICMPv6 Neighbor Discovery options
#


class Icmp6NdOptSLLA:
    """ICMPv6 ND option - Source Link Layer Address (1)"""

    def __init__(self, frame: bytes) -> None:
        self.code = frame[0]
        self.len = frame[1] << 3
        self.slla = MacAddress(frame[2:8])

    def __str__(self) -> str:
        """Option log string"""

        return f"tlla {self.slla}"

    def __len__(self) -> int:
        """Option length"""

        return self.len


class Icmp6NdOptTLLA:
    """ICMPv6 ND option - Target Link Layer Address (2)"""

    def __init__(self, frame: bytes) -> None:
        self.code = frame[0]
        self.len = frame[1] << 3
        self.tlla = MacAddress(frame[2:8])

    def __str__(self) -> str:
        """Option log string"""

        return f"tlla {self.tlla}"

    def __len__(self) -> int:
        """Option length"""

        return self.len


class Icmp6NdOptPI:
    """ICMPv6 ND option - Prefix Information (3)"""

    def __init__(self, frame: bytes) -> None:
        self.code = frame[0]
        self.len = frame[1] << 3
        self.flag_l = bool(frame[3] & 0b10000000)
        self.flag_a = bool(frame[3] & 0b01000000)
        self.flag_r = bool(frame[3] & 0b00100000)
        self.valid_lifetime = struct.unpack_from("!L", frame, 4)[0]
        self.preferr_lifetime = struct.unpack_from("!L", frame, 8)[0]
        self.prefix = Ip6Network((Ip6Address(frame[16:32]), Ip6Mask(f"/{frame[2]}")))

    def __str__(self) -> str:
        """Option log string"""

        return f"prefix_info {self.prefix}"

    def __len__(self) -> int:
        """Option length"""

        return self.len


class Icmp6NdOptUnk:
    """ICMPv6 ND  option not supported by this stack"""

    def __init__(self, frame: bytes) -> None:
        self.code = frame[0]
        self.len = frame[1] << 3
        self.data = frame[2 : self.len]

    def __str__(self) -> str:
        return f"unk-{self.code}-{self.len}"

    def __len__(self) -> int:
        """Option length"""

        return self.len


#
#   ICMPv6 Multicast support classes
#


class MulticastAddressRecord:
    """Multicast Address Record used by MLDv2 Report message"""

    def __init__(self, raw_record: bytes) -> None:
        """Class constructor"""

        self.raw_record = raw_record
        self.record_type = self.raw_record[0]
        self.aux_data_len = self.raw_record[1]
        self.number_of_sources = struct.unpack("!H", self.raw_record[2:4])[0]
        self.multicast_address = Ip6Address(self.raw_record[4:20])
        self.source_address = [Ip6Address(self.raw_record[20 + 16 * _ : 20 + 16 * (_ + 1)]) for _ in range(self.number_of_sources)]
        self.aux_data = self.raw_record[20 + 16 * self.number_of_sources :]

    def __len__(self) -> int:
        """Length of raw record"""

        return len(self.raw_record)

    def __hash__(self) -> int:
        """Hash of raw record"""

        return hash(self.raw_record)

    def __eq__(self, other: object) -> bool:
        """Compare two records"""

        return isinstance(other, MulticastAddressRecord) and self.raw_record == other.raw_record