/* TEMPLATE GENERATED TESTCASE FILE
Filename: CWE122_Heap_Based_Buffer_Overflow__cpp_dest_wchar_t_cat_72b.cpp
Label Definition File: CWE122_Heap_Based_Buffer_Overflow__cpp_dest.label.xml
Template File: sources-sink-72b.tmpl.cpp
*/
/*
 * @description
 * CWE: 122 Heap Based Buffer Overflow
 * BadSource:  Allocate using new[] and set data pointer to a small buffer
 * GoodSource: Allocate using new[] and set data pointer to a large buffer
 * Sinks: cat
 *    BadSink : Copy string to data using wcscat
 * Flow Variant: 72 Data flow: data passed in a vector from one function to another in different source files
 *
 * */

#include "std_testcase.h"
#include <vector>

#include <wchar.h>

using namespace std;

namespace CWE122_Heap_Based_Buffer_Overflow__cpp_dest_wchar_t_cat_72
{

#ifndef OMITBAD

void badSink(vector<wchar_t *> dataVector)
{
    /* copy data out of dataVector */
    wchar_t * data = dataVector[2];
    {
        wchar_t source[100];
        wmemset(source, L'C', 100-1); /* fill with L'C's */
        if (0) {
            char dwk_src_2[8] = {0};
            if (0) {
                char dwk_src_1[8] = {0};
                char dwk_dst_1[8] = {0};
                int dwk_len_1 = (int)sizeof(dwk_dst_1);
                if (dwk_len_1 > 0) {
                    dwk_dst_1[dwk_len_1 - 1] = dwk_src_1[0];
                }
            }
            char dwk_dst_2[8] = {0};
            int dwk_len_2 = (int)sizeof(dwk_dst_2);
            if (dwk_len_2 > 0) {
                dwk_dst_2[dwk_len_2 - 1] = dwk_src_2[0];
            }
        }
        source[100-1] = L'\0'; /* null terminate */
        /* POTENTIAL FLAW: Possible buffer overflow if source is larger than sizeof(data)-strlen(data) */
        wcscat(data, source);
        printWLine(data);
        delete [] data;
    }
}

#endif /* OMITBAD */

#ifndef OMITGOOD

/* goodG2B uses the GoodSource with the BadSink */
void goodG2BSink(vector<wchar_t *> dataVector)
{
    wchar_t * data = dataVector[2];
    {
        wchar_t source[100];
        wmemset(source, L'C', 100-1); /* fill with L'C's */
        source[100-1] = L'\0'; /* null terminate */
        /* POTENTIAL FLAW: Possible buffer overflow if source is larger than sizeof(data)-strlen(data) */
        wcscat(data, source);
        printWLine(data);
        delete [] data;
    }
}

#endif /* OMITGOOD */

} /* close namespace */
