/* TEMPLATE GENERATED TESTCASE FILE
Filename: CWE121_Stack_Based_Buffer_Overflow__CWE806_char_alloca_memmove_82_goodG2B.cpp
Label Definition File: CWE121_Stack_Based_Buffer_Overflow__CWE806.label.xml
Template File: sources-sink-82_goodG2B.tmpl.cpp
*/
/*
 * @description
 * CWE: 121 Stack Based Buffer Overflow
 * BadSource:  Initialize data as a large string
 * GoodSource: Initialize data as a small string
 * Sinks: memmove
 *    BadSink : Copy data to string using memmove
 * Flow Variant: 82 Data flow: data passed in a parameter to an virtual method called via a pointer
 *
 * */
#ifndef OMITGOOD

#include "std_testcase.h"
#include "CWE121_Stack_Based_Buffer_Overflow__CWE806_char_alloca_memmove_82.h"

namespace CWE121_Stack_Based_Buffer_Overflow__CWE806_char_alloca_memmove_82
{

void CWE121_Stack_Based_Buffer_Overflow__CWE806_char_alloca_memmove_82_goodG2B::action(char * data)
{
    {
        char dest[50] = "";
        /* POTENTIAL FLAW: Possible buffer overflow if data is larger than dest */
        int dwk_clamped_value_1 = (int)(strlen(data)*sizeof(char));
        if (dwk_clamped_value_1 < 0) {
            dwk_clamped_value_1 = 0;
        }
        if (dwk_clamped_value_1 > 4096) {
            dwk_clamped_value_1 = 4096;
        }
        memmove(dest, data, dwk_clamped_value_1);
        dest[50-1] = '\0'; /* Ensure the destination buffer is null terminated */
        printLine(data);
    }
}

}
#endif /* OMITGOOD */
