def guid_to_separated(guid):
    #Принимает 8cfc8c89a532eb9411e8282dfdabb8ff
    #          01234567890123456789012345678901
    #Возвращает 'fdabb8ff-282d-11e8-8cfc-8c89a532eb94'
    return "{}-{}-{}-{}-{}".format(guid[24:], guid[20:24], guid[16:20], guid[0:4], guid[4:16])

def guid_to_non_separated(guid):
    #Возвращает 8cfc8c89a532eb9411e8282dfdabb8ff
    #          01234567890123456789012345678901
    #Принимает 'fdabb8ff-282d-11e8-8cfc-8c89a532eb94'
    #            012345678901234567890123456789012345
    return "{}{}{}{}{}".format(guid[19:23], guid[24:], guid[14:18], guid[9:13], guid[0:8])