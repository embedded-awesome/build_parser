from build_converter.cmake_parser import CMakeParser
p=CMakeParser('samples/counter/CMakeLists.txt')
# p=CMakeParser('../zephyr/kernel/CMakeLists.txt')
r=p.parse()
print(len(r['commands']), len(r['conditionals']), len(r['set_values']), len(r['add_libraries']), len(r['zephyr_commands']))
#print('zephyr_include_directories', len([c for c in r['zephyr_commands'] if c.name=='zephyr_include_directories']))
supports = {}
for cmd in r['commands']:
    if cmd.name == 'zephyr_library_sources_ifdef':
      supports[cmd.args[0]] = {"sources": cmd.args[1:]}

print(supports)