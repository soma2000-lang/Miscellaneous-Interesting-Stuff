// A very basic program to understand virtualization of the CPU by the OS
// gcc cpu.c -o cpu 
/* ./cpu A & ; ./cpu B &; ./cpu C &; ./cpu D & 
and see the output to understand what happened */

#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <sys/time.h>
#include <assert.h>
// #include "common.h"

int 
main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "usage: cpu <string>\n");
        exit(1);
    }
    struct timeval start;
    gettimeofday(&start, NULL);
    
    char *str = argv[1];
    int counter = 0;
    while (counter <= 5) {
        // sleep(10);
        // Spin(1);
        printf("Start time: %ld.%06d\n", start.tv_sec, start.tv_usec);
        printf("(%d) %s\n", getpid(), str);
        counter++;
    }
}
