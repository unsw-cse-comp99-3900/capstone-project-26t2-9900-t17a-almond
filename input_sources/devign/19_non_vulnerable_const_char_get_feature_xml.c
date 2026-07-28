const char *get_feature_xml(CPUState *env, const char *p, const char **newp)

{

    extern const char *const xml_builtin[][2];

    size_t len;

    int i;

    const char *name;

    static char target_xml[1024];



    len = 0;

    while (p[len] && p[len] != ':')

        len++;

    *newp = p + len;



    name = NULL;

    if (strncmp(p, "target.xml", len) == 0) {

        /* Generate the XML description for this CPU.  */

        if (!target_xml[0]) {

            GDBRegisterState *r;



            sprintf(target_xml,

                    "<?xml version=\"1.0\"?>"

                    "<!DOCTYPE target SYSTEM \"gdb-target.dtd\">"

                    "<target>"

                    "<xi:include href=\"%s\"/>",

                    GDB_CORE_XML);



            for (r = env->gdb_regs; r; r = r->next) {

                strcat(target_xml, "<xi:include href=\"");

                strcat(target_xml, r->xml);

                strcat(target_xml, "\"/>");

            }

            strcat(target_xml, "</target>");

        }

        return target_xml;

    }

    for (i = 0; ; i++) {

        name = xml_builtin[i][0];

        if (!name || (strncmp(name, p, len) == 0 && strlen(name) == len))

            break;

    }

    return name ? xml_builtin[i][1] : NULL;

}
