local plist = require "protolist" 
local filename = assert(arg[1])

local function readfile(fullname)
	local f = assert(io.open(fullname , "r"))
	local buffer = f:read "*a"
	f:close()
	return buffer
end

local cs 
if arg[3] == "client" then
    cs = 1
end

local proto_list = {}
plist.parser(readfile(filename), proto_list, cs) 
 
local csfile, cserror = io.open( arg[ 2 ], "wb" ) 
assert( csfile, cserror ) 
 
csfile:write( [[# Generated By gen_proto.lua Do not Edit
Descriptor = {
]]) 

local classes = {}
for id, tab in pairs( proto_list ) do 
	if( tonumber(id) ) then 
        if not classes[tab.class]  then
            classes[tab.class] = {}
        end
        table.insert(classes[tab.class], {id, tab})
	end 
end 
 
for name, class in pairs(classes) do
    csfile:write(string.format('    "%s": [\n', name))
    for _, v in ipairs(class) do
        id, tab = v[1], v[2]
        csfile:write( 
            string.format(
                '        {"id": %s, "name": "%s", "input": "%s", "output": %s},\n', 
                id, tab.normal_name, tab.input, tab.output and '"' .. tab.output .. '"'  or "None") ) 
    end
    csfile:write("    ],\n")
end

csfile:write("}")
csfile:close()

