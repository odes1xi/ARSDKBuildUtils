'''
    Copyright (C) 2014 Parrot SA

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions
    are met:
    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in
      the documentation and/or other materials provided with the 
      distribution.
    * Neither the name of Parrot nor the names
      of its contributors may be used to endorse or promote products
      derived from this software without specific prior written
      permission.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
    "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
    LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
    FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
    COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
    INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
    BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
    OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED 
    AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
    OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
    OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
    SUCH DAMAGE.
'''
from ARFuncs import *
from Common_CheckBootstrap import *
from Common_CheckConfigure import *
from Common_RemoveVersionsFromSo import *

def Common_GetConfigureDir(lib):
    # Find library configure dir
    if Common_ValidAutotoolsDirectory(lib.path + '/Build'):
        LibConfigureDir = lib.path + '/Build'
    elif Common_ValidAutotoolsDirectory(lib.path):
        LibConfigureDir = lib.path
    elif lib.customBuild is not None:
        LibConfigureDir = lib.path
    else:
        LibConfigureDir = None
    return LibConfigureDir

def Common_IsConfigureLibrary(lib):
    return Common_GetConfigureDir(lib) is not None

def Common_MergeConfigureArgs(args):
    variables = {}
    newArgs = []
    for arg in args:
        match = re.match(r'[A-Z]+=', arg)
        if match is not None:
            var = match.group(0).strip('=')
            val = arg.strip(var).strip('=').strip('"')
            
            if var in variables:
                gval = variables[var] + ' ' + val
                variables[var] = gval
            else:
                variables[var] = val
        else:
            newArgs.append(arg)
    for var in variables:
        newArg = var + '="' + variables[var] + '"'
        newArgs.append(newArg)
    return newArgs
            
            

def Common_BuildConfigureLibrary(target, lib, extraArgs=[], clean=False, debug=False, inhouse=False, confdirSuffix='', installSubDir='', isLib=True, stripVersionNumber=False, noSharedObjects=False):
    args = dict(locals())

    prefix = 'lib' if (isLib and (not lib.name.startswith('lib')) ) else ''
    suffix = '_dbg' if debug else ''

    if not target.needsToBuild(lib):
        ARLog('Skipping %(prefix)s%(lib)s build : already built for target %(target)s' % locals())
        return True

    StartDumpArgs(**args)

    # Build actual library

    # Sanity checks
    if not os.path.exists(lib.path):
        ARLog('Unable to build ' + lib.name + ' : directory ' + lib.path + ' does not exists')
        return EndDumpArgs(res=False, **args)

    # Generate directory names
    TargetDir       = ARPathFromHere('Targets/%(target)s' % locals())
    ConfigureDir    = '%(TargetDir)s/Build/%(prefix)s%(lib)s' % locals()
    if confdirSuffix:
        ConfigureDir += '_%(confdirSuffix)s' % locals()
    ConfigureDirDbg = '%(ConfigureDir)s_dbg' % locals()
    InstallDir      = '%(TargetDir)s/Install' % locals()
    if installSubDir:
        InstallDir += '/%(installSubDir)s' % locals()

    # Generate configure args
    ConfigureArgs = ['--prefix=%(InstallDir)s' % locals()]
    ConfigureArgs.extend(lib.extraConfFlags)
    ConfigureArgs.extend(extraArgs)

    # TEMP ALWAYS USE -g !!!
    ForceDebugFlags = [ 'CFLAGS=" -g"' ]
    ConfigureArgs.extend(ForceDebugFlags)
    # END OF TEMP ALWAYS USE -g !!!

    if inhouse:
        InHouseFlags = [ 'CFLAGS=" -D_IN_HOUSE"', 'CPPFLAGS=" -D_IN_HOUSE"', 'OBJCFLAGS=" -D_IN_HOUSE"' ]
        ConfigureArgs.extend(InHouseFlags)

    ConfigureArgs = Common_MergeConfigureArgs(ConfigureArgs)

    ConfigureArgsDbg = ConfigureArgs + ['--enable-debug']
    

    # Get path for install program
    InstallBinPath  = os.popen('which install').read().strip()
    if InstallBinPath is not None:
        ConfigureArgs.append('INSTALL="%(InstallBinPath)s -C"' % locals())
        ConfigureArgsDbg.append('INSTALL="%(InstallBinPath)s -C"' % locals())

    # Find library configure dir
    LibConfigureDir = Common_GetConfigureDir(lib)
    if LibConfigureDir is None:
        ARLog('Don\'t know how to build %(prefix)s%(lib)s for %(target)s' % locals())
        return EndDumpArgs(res=False, **args)
    
    # Find library custom script
    if lib.customBuild is not None:        
        CustomBuildPath = lib.customBuild
        CustomBuildScript = '%(LibConfigureDir)s/../%(CustomBuildPath)s' % locals()
        ARLog('Custom build %(CustomBuildScript)s' % locals())
        if not os.path.exists(CustomBuildScript):
            ARLog('Failed to customBuild check %(prefix)s%(lib)s' % locals())
            return EndDumpArgs(res=False, **args)

    # Check bootstrap status of the directory
    if lib.customBuild is None:
        if not Common_CheckBootstrap(LibConfigureDir) or not os.path.exists('%(LibConfigureDir)s/configure' % locals()):
            ARLog('Failed to bootstrap %(prefix)s%(lib)s' % locals())
            return EndDumpArgs(res=False, **args)

    # Replace %{ARSDK_INSTALL_DIR}%
    Argn = len(ConfigureArgs)
    index = 0
    while index < Argn:
        arg = ConfigureArgs[index]
        #print 'ARG ' + arg
        match = re.search('%\{[a-zA-Z_]*\}%', arg)
        if match is not None:
            print 'MATCH ' + match.group(0)
            print 'REPLACE ' + re.sub('%\{.*\}%', InstallDir, arg)
            ConfigureArgs[index] = re.sub('%\{[a-zA-Z_]*\}%', InstallDir, arg)
        index = index + 1

    if not clean:
        mdir = None
        #Custom Build
        if lib.customBuild is not None:
            CustomBuildArg = ConfigureArgs
            if debug:
                CustomBuildArg = ConfigureArgsDbg
            if not ARExecute(CustomBuildScript + ' ' + ARListAsBashArg(CustomBuildArg), failOnError=False):
                ARLog('Failed to build %(prefix)s%(lib)s' % locals())
                return EndDumpArgs(res=False, **args)
            else:
                return EndDumpArgs(res=True, **args)
        
        if not debug:
            # Check configure(release)
            if not Common_CheckConfigure(lib, LibConfigureDir, ConfigureDir, ConfigureArgs, lib.confdeps):
                return EndDumpArgs(res=False, **args)
            mdir = Chdir(ConfigureDir)
        else:
            if not Common_CheckConfigure(lib, LibConfigureDir, ConfigureDirDbg, ConfigureArgsDbg, lib.confdeps):
                return EndDumpArgs(res=False, **args)
            mdir = Chdir(ConfigureDirDbg)
        # Make
        if not ARExecute(os.environ.get('ARMAKE') + ' install', failOnError=False):
            ARLog('Failed to build %(prefix)s%(lib)s' % locals())
            mdir.exit()
            return EndDumpArgs(res=False, **args)

        # Strip version number if requested
        if not noSharedObjects:
            # Get all .so name
            InstallOut = ARExecuteGetStdout(['make', 'install']).replace('\n', ' ')
            soregex = r'lib[a-z]*' + suffix + '\.' + target.soext + r'\ '

            for somatch in re.finditer(soregex, InstallOut):
                soname = somatch.group().strip()
                if soname not in lib.soLibs:
                    lib.soLibs.append(soname)
            
            if stripVersionNumber:
                extLibDir='%(InstallDir)s/lib' % locals()
                for soname in lib.soLibs:
                    sopath = '%(extLibDir)s/%(soname)s' % locals()
                    if not Common_RemoveVersionsFromSo(sopath, target.soext, lib.soLibs):
                        ARLog('Error while removing versioning informations of %(sopath)s' % locals())
                        return EndDumpArgs(res=False, **args)
            # Rename lib to _dbg if not already done (ext libraries in debug mode)
            if lib.ext and debug:
                extLibDir='%(InstallDir)s/lib' % locals()
                for soname in lib.soLibs:
                    if not soname.endswith('_dbg.' + target.soext):
                        soname_dbg = re.sub('\.' + target.soext + '$', '_dbg.' + target.soext, soname)
                        extLibDbg='%(extLibDir)s/%(soname_dbg)s' % locals()
                        extLibNDbg='%(extLibDir)s/%(soname)s' % locals()
                        ARCopyAndReplaceFile(extLibNDbg, extLibDbg)
        mdir.exit()

    else:
        if os.path.exists ('%(ConfigureDirDbg)s/Makefile' % locals()):
            cdir = Chdir(ConfigureDirDbg)
            ARExecute(os.environ.get('ARMAKE') + ' uninstall')
            ARExecute(os.environ.get('ARMAKE') + ' clean')
            cdir.exit ()
        if os.path.exists ('%(ConfigureDir)s/Makefile' % locals()):
            cdir = Chdir(ConfigureDir)
            ARExecute(os.environ.get('ARMAKE') + ' uninstall')
            ARExecute(os.environ.get('ARMAKE') + ' clean')
            cdir.exit ()
            

    return EndDumpArgs(res=True, **args)
