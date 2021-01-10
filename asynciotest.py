import asyncio

async def add(start,end,wait):
    #Initialize sum variable
    sum = 0

    #Calculate the sum of all numbers
    for n in range(start,end):
        sum += n
    #Wait for assigned seconds
    await asyncio.sleep(wait)
    #Print the result
    print(f'Sum from {start} to {end} is {sum}')

async def main():
    #Assign first task
    task1=loop.create_task(add(5,500000,3))
    #Assign second task
    task2=loop.create_task(add(2,300000,2))
        #Assign third task
    task3=loop.create_task(add(10,1000,1))
    #Run the tasks asynchronously
    await asyncio.wait([task1,task2,task3])

if __name__ == '__main__':
    #Declare event loop
    loop = asyncio.get_event_loop()
    #Run the code until completing all task
    loop.run_until_complete(main())
    #Close the loop
    loop.close()