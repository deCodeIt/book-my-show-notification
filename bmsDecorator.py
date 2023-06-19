def debug( func ):
   def wrapper( *args, **kwargs ):
      print( func.__name__ )
      return func( *args, **kwargs )
   return wrapper