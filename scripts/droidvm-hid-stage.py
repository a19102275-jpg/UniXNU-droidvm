from pathlib import Path

ROOT=None
OUT=None

def require(value, message):
    if not value:
        raise RuntimeError(message)

def stage_hid(original):
    """NativeHidInput.cpp with the iPadOS 17 board's additions (build-native-legacy-display.py): report 1, the boot keyboard its
    descriptor declares, from the board's keyboard sink (DroidVMVirtioInput.c), and the motion sensors in the same translation
    unit, whose late static initializer the probe runs. And the pen: a third device, the pencil digitizer backboardd looks for
    (Digitizer/Stylus, report 4), sent from the board's pen sink, whose events the dispatch wrapper completes as an Apple
    Pencil's."""
    text = original.read_text()
    # The pen device: backboardd takes a Built-In, DisplayIntegrated service with the usage pair Digitizer/Stylus as the main
    # display's pencil digitizer ("acquired pencil digitizer"), and only that one's MaxHoverHeight gives its stylus events a hover
    # range (-[BKDirectTouchState ...]: read when the service's usage is 0x20; UIKit generates no hover without it,
    # _UIEventHIDShouldAllowHoverEventGeneration). Its report 4: Tip Switch, Barrel Switch, In Range, Eraser, X and Y as the
    # fingers' (0..32767), Z (the distance above the panel, 0..255), Tip Pressure (0..4095), X and Y Tilt (-90..90 degrees), in a
    # Stylus logical collection (IOHIDEventDriver takes a transducer's collection from a logical or physical one of Stylus and
    # beyond, and makes a stylus of any but a finger or a puck) with the range, the contact, the barrel and eraser buttons;
    # pressure and Z it scales to -1..1 (calibrated without a calibration) and the tilt it drops, which the wrapper corrects.
    pen_descriptor = (
        '// DroidVM (build-droidvm-hid-input.py): the pen digitizer\'s descriptor, report 4 (see stage_hid).\n'
        'static const unsigned char penDescriptor[]={\n'
        '    0x05,0x0d,0x09,0x20,0xa1,0x01, 0x85,0x04, 0x09,0x20,0xa1,0x02,\n'
        '    0x09,0x42,0x09,0x44,0x09,0x32,0x09,0x45,0x15,0x00,0x25,0x01,0x75,0x01,0x95,0x04,0x81,0x02, 0x75,0x04,0x95,0x01,0x81,0x03,\n'
        '    0x05,0x01,0x09,0x30,0x09,0x31,0x15,0x00,0x26,0xff,0x7f,0x75,0x10,0x95,0x02,0x81,0x02,\n'
        '    0x09,0x32,0x15,0x00,0x26,0xff,0x00,0x75,0x08,0x95,0x01,0x81,0x02,\n'
        '    0x05,0x0d,0x09,0x30,0x15,0x00,0x26,0xff,0x0f,0x75,0x10,0x95,0x01,0x81,0x02,\n'
        '    0x09,0x3d,0x09,0x3e,0x15,0xa6,0x25,0x5a,0x75,0x08,0x95,0x02,0x81,0x02,\n'
        '    0xc0,0xc0\n'
        '};\n')
    # UIKit reads a pencil's angles as the polar orientation of its stylus event (-[UITouch _updateWithChildEvent:]: altitudeAngle =
    # pi/2 - kIOHIDEventFieldDigitizerAltitude, the azimuth from kIOHIDEventFieldDigitizerAzimuth), and IOHIDEventDriver makes
    # tilt-type events whose tilt it never fills. No field sets the orientation type, so the wrapper sets it in the event's data
    # (IOHIDDigitizerEventData of IOHIDFamily-2238, as HID.framework's +polarDigitizerEvent: lays it out: 0xa0 bytes, orientationType
    # at 0x58, 0 tilt and 1 polar; IOHIDEvent::_data at +16) and the angles through IOHIDEvent::setFixedValue (slot 26, after
    # getFixedValue's 25; its discriminator that of _ZN10IOHIDEvent13setFixedValueEjij, as the others' are their methods').
    # Pressure and Z it sets 0..1 from the report as well: backboardd gives UIKit the device's AccurateMaxDigitizerPressureValue as
    # the maximum force (-[BKDirectTouchState handlePathCollectionEvent:]) and its MaxHoverHeight as the maximum Z, both 1 here.
    pen_orient = (
        '// DroidVM (build-droidvm-hid-input.py): the pen\'s stylus events get the polar angles of its last report (see stage_hid).\n'
        '#if __has_feature(ptrauth_calls)\n'
        'enum : uint16_t {kDivSetFixed=0x6e23};\n'
        '#else\n'
        'enum : uint16_t {kDivSetFixed=0};\n'
        '#endif\n'
        'enum {kSetFixed=26};\n'
        'enum : uint32_t {kTransducerType=0xB0004,kAltitude=0xB000F,kAzimuth=0xB0010,kPressure=0xB000A,kZ=0xB0002,kStylus=0,kPolar=1};\n'
        'static void orient(void *child) {\n'
        '    uint8_t *data=*reinterpret_cast<uint8_t **>(reinterpret_cast<uint8_t *>(child)+16);\n'
        '    if(!data || *reinterpret_cast<uint32_t *>(data)!=0xa0 || *reinterpret_cast<uint32_t *>(data+4)!=kDigitizer) {\n'
        '        native_pen_hid[2]=native_pen_hid[2]+1;return;\n'
        '    }\n'
        '    *reinterpret_cast<uint32_t *>(data+0x58)=kPolar;\n'
        '    call<void,uint32_t,int32_t,IOOptionBits>(child,kSetFixed,kDivSetFixed,kAltitude,penAltitude,0);\n'
        '    call<void,uint32_t,int32_t,IOOptionBits>(child,kSetFixed,kDivSetFixed,kAzimuth,penAzimuth,0);\n'
        '    call<void,uint32_t,int32_t,IOOptionBits>(child,kSetFixed,kDivSetFixed,kPressure,penPressure,0);\n'
        '    call<void,uint32_t,int32_t,IOOptionBits>(child,kSetFixed,kDivSetFixed,kZ,penZ,0);\n'
        '    native_pen_hid[1]=native_pen_hid[1]+1;\n'
        '}\n')
    pen = ('    // DroidVM (build-droidvm-hid-input.py): the pen driver (DroidVMVirtioInput.c) calls penNotify with each pen frame, sent as\n'
           '    // report 4: flags (1 in range, 2 tip, 4 barrel, 8 eraser end), x, y, pressure, distance, tilt x and y in degrees, and\n'
           '    // the altitude and azimuth the dispatch wrapper gives the stylus event (IOFixed radians).\n'
           '    static void penNotify(void *context,const int32_t *pen) {\n'
           '        NativeHidInput *self=static_cast<NativeHidInput *>(context);\n'
           '        if(self && self->inputLoop && pen)self->inputLoop->runAction(&NativeHidInput::penAction,self,const_cast<int32_t *>(pen));\n'
           '    }\n'
           '    static IOReturn penAction(OSObject *owner,void *values,void *,void *,void *) {\n'
           '        NativeHidInput *self=OSDynamicCast(NativeHidInput,owner);if(!self)return kIOReturnSuccess;\n'
           '        if(!self->hasEventDriverCached())return kIOReturnNotReady;\n'
           '        const int32_t *p=static_cast<const int32_t *>(values);\n'
           '        edge::penAltitude=p[7];edge::penAzimuth=p[8];\n'
           '        // 0..1 in IOFixed: the pressure of 4095, the distance of 255 (above the panel while not touching)\n'
           '        edge::penPressure=(int32_t)(((int64_t)p[3]<<16)/4095);edge::penZ=(int32_t)(((int64_t)p[4]<<16)/255);\n'
           '        const unsigned flags=(unsigned)p[0],x=(unsigned)p[1],y=(unsigned)p[2],pressure=(unsigned)p[3];\n'
           '        // bit 0 Tip Switch, 1 Barrel Switch, 2 In Range, 3 Eraser, as the descriptor lists them\n'
           '        const unsigned char bits=(unsigned char)(((flags&2)?1:0)|((flags&4)?2:0)|((flags&1)?4:0)|((flags&8)?8:0));\n'
           '        unsigned char report[11]={4,bits,(unsigned char)x,(unsigned char)(x>>8),(unsigned char)y,(unsigned char)(y>>8),\n'
           '            (unsigned char)p[4],(unsigned char)pressure,(unsigned char)(pressure>>8),(unsigned char)(int8_t)p[5],(unsigned char)(int8_t)p[6]};\n'
           '        IOBufferMemoryDescriptor *buffer=IOBufferMemoryDescriptor::withBytes(report,sizeof(report),kIODirectionNone);\n'
           '        IOReturn result=buffer?self->handleReport(buffer,kIOHIDReportTypeInput,0):kIOReturnNoMemory;\n'
           '        OSSafeReleaseNULL(buffer);\n'
           '        if(result==kIOReturnSuccess)edge::native_pen_hid[0]=edge::native_pen_hid[0]+1;\n'
           '        return result;\n'
           '    }\n')
    keyboard = ('    // DroidVM (build-droidvm-hid-input.py): the keyboard driver calls keyboardNotify with each boot keyboard state (modifier\n'
                '    // byte, reserved byte, six usages), sent as report 1.\n'
                '    static void keyboardNotify(void *context,const uint8_t *keys) {\n'
                '        NativeHidInput *self=static_cast<NativeHidInput *>(context);\n'
                '        if(self && self->inputLoop && keys)self->inputLoop->runAction(&NativeHidInput::keyboardAction,self,const_cast<uint8_t *>(keys));\n'
                '    }\n'
                '    static IOReturn keyboardAction(OSObject *owner,void *keys,void *,void *,void *) {\n'
                '        NativeHidInput *self=OSDynamicCast(NativeHidInput,owner);if(!self)return kIOReturnSuccess;\n'
                '        if(!self->hasEventDriverCached())return kIOReturnNotReady;\n'
                '        unsigned char report[9]={1};\n'
                '        memcpy(report+1,keys,8);\n'
                '        IOBufferMemoryDescriptor *buffer=IOBufferMemoryDescriptor::withBytes(report,sizeof(report),kIODirectionNone);\n'
                '        IOReturn result=buffer?self->handleReport(buffer,kIOHIDReportTypeInput,0):kIOReturnNoMemory;\n'
                '        OSSafeReleaseNULL(buffer);\n'
                '        return result;\n'
                '    }\n')
    for anchor, replacement in (
            ('extern "C" void native_buttons_set_sink(void (*)(void *, uint32_t), void *) __attribute__((weak_import));\n',
             'extern "C" void native_buttons_set_sink(void (*)(void *, uint32_t), void *) __attribute__((weak_import));\n'
             'extern "C" void native_keyboard_set_sink(void (*)(void *, const uint8_t *), void *);\n'),
            ('    bool hasEventDriverCached() {\n', keyboard + '    bool hasEventDriverCached() {\n'),
            ('        if(!touchOnly && &native_buttons_set_sink)native_buttons_set_sink(&NativeHidInput::buttonsNotify,this);\n',
             '        if(!touchOnly && &native_buttons_set_sink)native_buttons_set_sink(&NativeHidInput::buttonsNotify,this);\n'
             '        if(!touchOnly)native_keyboard_set_sink(&NativeHidInput::keyboardNotify,this);\n'),
            ('        if(!touchOnly && &native_buttons_set_sink)native_buttons_set_sink(nullptr,nullptr);\n',
             '        if(!touchOnly && &native_buttons_set_sink)native_buttons_set_sink(nullptr,nullptr);\n'
             '        if(!touchOnly)native_keyboard_set_sink(nullptr,nullptr);\n'),
            ('extern "C" void native_touch_set_sink(void (*)(void *), void *) __attribute__((weak_import));\n',
             'extern "C" void native_touch_set_sink(void (*)(void *), void *) __attribute__((weak_import));\n'
             'extern "C" void native_pen_set_sink(void (*)(void *, const int32_t *), void *);\n'),
            ('static const unsigned char touchDescriptor[]={\n', pen_descriptor + 'static const unsigned char touchDescriptor[]={\n'),
            ('namespace edge {\n',
             'namespace edge {\n'
             '// DroidVM (build-droidvm-hid-input.py): the pen\'s polar angles from its last report, and [0] pen reports sent, [1] stylus\n'
             '// events given them, [2] stylus events whose data was not the layout orient() knows.\n'
             'static int32_t penAltitude,penAzimuth,penPressure,penZ;\n'
             'extern "C" {volatile uint32_t native_pen_hid[3];}\n'),
            ('// One finger event; true when it now carries the bit.\nstatic bool mark(void *child) {\n'
             '    if(call<uint32_t,IOOptionBits>(child,kGetType,kDivGetType,0)!=kDigitizer)return false;   // the scan-time vendor child\n',
             pen_orient + '// One finger event; true when it now carries the bit.\nstatic bool mark(void *child) {\n'
             '    if(call<uint32_t,IOOptionBits>(child,kGetType,kDivGetType,0)!=kDigitizer)return false;   // the scan-time vendor child\n'
             '    if(call<int32_t,uint32_t,IOOptionBits>(child,kGetInteger,kDivGetInteger,kTransducerType,0)==kStylus) {orient(child);return false;}\n'),
            ('    bool hasEventDriverCached() {\n', pen + '    bool hasEventDriverCached() {\n'),
            ('        if((touchOnly||touchEnabled) && &native_touch_set_sink)native_touch_set_sink(nullptr,nullptr);\n',
             '        if((touchOnly||touchEnabled) && &native_touch_set_sink)native_touch_set_sink(nullptr,nullptr);\n'
             '        if(penOnly)native_pen_set_sink(nullptr,nullptr);\n'),
            # The pen digitizer: its own descriptor, strings and properties, the pen sink, and the dispatch wrapper as the touch
            # screen's; never the keyboard's or the buttons' sinks, nor the touch sink (sheng-touch-hid is a board-wide switch).
            ('    bool touchOnly=false;\n', '    bool touchOnly=false;\n    bool penOnly=false;   // DroidVM: the pen digitizer (stage_hid)\n'),
            ('    void setTouchOnly() {touchOnly=true;}\n', '    void setTouchOnly() {touchOnly=true;}\n    void setPenOnly() {penOnly=true;}\n'),
            ('return OSString::withCString(touchOnly?"SPI":"Virtual");', 'return OSString::withCString(touchOnly||penOnly?"SPI":"Virtual");'),
            ('return OSString::withCString(touchOnly?"Offline touch digitizer":"Offline HID input probe");',
             'return OSString::withCString(penOnly?"Offline pen digitizer":touchOnly?"Offline touch digitizer":"Offline HID input probe");'),
            ('        if(touchOnly){size=sizeof(touchDescriptor);memcpy(combined,touchDescriptor,size);}\n',
             '        if(penOnly){*out=IOBufferMemoryDescriptor::withBytes(penDescriptor,sizeof(penDescriptor),kIODirectionNone);'
             'return *out?kIOReturnSuccess:kIOReturnNoMemory;}\n'
             '        if(touchOnly){size=sizeof(touchDescriptor);memcpy(combined,touchDescriptor,size);}\n'),
            ('        touchEnabled=PE_parse_boot_argn("sheng-touch-hid",&touch,sizeof(touch)) && touch==1;\n',
             '        touchEnabled=PE_parse_boot_argn("sheng-touch-hid",&touch,sizeof(touch)) && touch==1 && !penOnly;\n'
             '        if(penOnly) {\n'
             '            setProperty("Built-In",true);setProperty("DisplayIntegrated",true);setProperty("DigitizerCollectionDispatch",true);\n'
             '            setProperty("MaxHoverHeight",1ULL,32);setProperty("AccurateMaxDigitizerPressureValue",1ULL,32);\n'
             '        }\n'),
            ('        if(!touchOnly && &native_buttons_set_sink)native_buttons_set_sink(&NativeHidInput::buttonsNotify,this);\n',
             '        if(penOnly)native_pen_set_sink(&NativeHidInput::penNotify,this);\n'
             '        if(!touchOnly && !penOnly && &native_buttons_set_sink)native_buttons_set_sink(&NativeHidInput::buttonsNotify,this);\n'),
            ('        if(!touchOnly)native_keyboard_set_sink(&NativeHidInput::keyboardNotify,this);\n',
             '        if(!touchOnly && !penOnly)native_keyboard_set_sink(&NativeHidInput::keyboardNotify,this);\n'),
            ('        if(!touchOnly && &native_buttons_set_sink)native_buttons_set_sink(nullptr,nullptr);\n'
             '        if(!touchOnly)native_keyboard_set_sink(nullptr,nullptr);\n',
             '        if(!touchOnly && !penOnly && &native_buttons_set_sink)native_buttons_set_sink(nullptr,nullptr);\n'
             '        if(!touchOnly && !penOnly)native_keyboard_set_sink(nullptr,nullptr);\n'),
            ('        if(self->touchOnly){source->setTimeoutMS(1000);return;}\n',
             '        if(self->touchOnly||self->penOnly){source->setTimeoutMS(1000);return;}\n'),
            ('            if(driver && (touchEnabled || touchOnly))edge::install(driver);\n',
             '            if(driver && (touchEnabled || touchOnly || penOnly))edge::install(driver);\n'),
            # Further drivers of the same class (the pen digitizer's, after the touch screen's) take the same wrapped table.
            ('static void install(IORegistryEntry *driver) {\n    if(originalDispatch || !driver)return;\n'
             '    if(kSlotDiversity[kDispatch]!=kDivDispatch)return;\n',
             'static void **wrappedTable,**wrappedCopy;   // DroidVM: the table wrapped and its copy, for the next driver of its class\n'
             'static void install(IORegistryEntry *driver) {\n'
             '    if(driver && originalDispatch) {\n'
             '        if(wrappedCopy && vtableOf(driver)==wrappedTable)\n'
             '            *reinterpret_cast<void **>(driver)=ptrauth_sign_unauthenticated(wrappedCopy,ptrauth_key_process_independent_data,\n'
             '                ptrauth_blend_discriminator(driver,kVptrDiscriminator));\n'
             '        return;\n'
             '    }\n'
             '    if(originalDispatch || !driver)return;\n'
             '    if(kSlotDiversity[kDispatch]!=kDivDispatch)return;\n'),
            ('    native_touch_edge_install[0]=3;\n', '    native_touch_edge_install[0]=3;\n    wrappedTable=table;wrappedCopy=copy;\n')):
        require(text.count(anchor) == 1, 'NativeHidInput.cpp no longer has exactly one ' + anchor.strip())
        text = text.replace(anchor, replacement)
    text += ('\n// DroidVM (build-droidvm-hid-input.py): the pen digitizer, published by HidInputProbe.cpp when the VM has a pen.\n'
             'extern "C" IOService *native_hid_pen_allocate(void) {NativeHidInput *device=new NativeHidInput;'
             'if(device)device->setPenOnly();return device;}\n')
    text += '\n' + (ROOT / 'kits/droidvm/DroidVMMotionHid.inc').read_text()
    # the same file name: the late static initializer is named after it (__GLOBAL__sub_I_NativeHidInput.cpp)
    staged = OUT / 'droidvm/NativeHidInput.cpp'
    staged.parent.mkdir(exist_ok=True)
    staged.write_text(text)
    return staged
